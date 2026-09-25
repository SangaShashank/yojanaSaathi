"""
Yojana Saathi - Deterministic Eligibility Engine
================================================
Pure Python rules engine evaluating citizen profiles against versioned government scheme rules.
Contains ZERO LLM / probabilistic decision-making.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from backend.app.schemas.profile import CitizenProfile
from backend.app.schemas.scheme import ConditionDefinition, SchemeDefinition
from backend.app.schemas.eligibility import (
    CriterionResult,
    CriterionStatus,
    MultiSchemeEvaluationResult,
    SchemeEvaluationResult,
    SchemeOutcome,
)
from backend.app.rules.operators import get_operator
from backend.app.services.scheme_loader import load_all_schemes


def _check_applies_only_if(clause: str, profile: CitizenProfile) -> Tuple[bool, bool]:
    """
    Evaluates an 'applies_only_if' clause (e.g. 'user_state == Telangana' or 'category == widow').
    
    Returns:
        (applies, is_known):
        - If condition is known to apply: (True, True)
        - If condition is known NOT to apply: (False, True)
        - If field is unknown: (False, False)
    """
    clause_clean = clause.strip()
    if "==" in clause_clean:
        parts = [p.strip() for p in clause_clean.split("==")]
        field_name = parts[0]
        expected_val = parts[1]

        # Normalize field name if prefixed
        if field_name == "user_state":
            field_name = "state"

        actual_val, is_known = profile.get_field_value(field_name)
        if not is_known:
            return False, False

        match = str(actual_val).strip().lower() == str(expected_val).strip().lower()
        return match, True

    # Fallback if clause format is unrecognized
    return True, True


def _check_scope_applicability(scope: str, profile: CitizenProfile) -> Tuple[bool, bool]:
    """
    Evaluates if a scoped condition applies to the applicant based on community and residence type.
    Example scopes: 'sc_st_or_urban_bc_ebc', 'rural_bc_ebc'.
    
    Returns:
        (applies, is_known)
    """
    community, has_community = profile.get_field_value("community")
    residence, has_residence = profile.get_field_value("residence_type")

    if scope == "rural_bc_ebc":
        if not has_residence and not has_community:
            return False, False
        is_rural = str(residence).strip().lower() == "rural" if has_residence else False
        is_bc_ebc = str(community).strip().lower() in ["bc", "ebc", "bc_ebc"] if has_community else False
        if has_residence and not is_rural:
            return False, True
        return (is_rural and is_bc_ebc), (has_residence and has_community)

    if scope == "sc_st_or_urban_bc_ebc":
        if not has_residence and not has_community:
            return False, False
        is_sc_st = str(community).strip().lower() in ["sc", "st", "sc_st"] if has_community else False
        is_urban = str(residence).strip().lower() == "urban" if has_residence else False
        is_bc_ebc = str(community).strip().lower() in ["bc", "ebc", "bc_ebc"] if has_community else False
        if is_sc_st:
            return True, True
        return (is_urban and is_bc_ebc), (has_residence and has_community)

    return True, True


def evaluate_any_of_condition(
    condition: ConditionDefinition, profile: CitizenProfile
) -> CriterionResult:
    """
    Evaluates compound 'any_of' conditions (e.g. income qualifying criteria in PMMVY).
    """
    sub_conditions = condition.value
    if not isinstance(sub_conditions, list):
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.UNKNOWN,
            actual=None,
            expected=condition.value,
            operator="any_of",
            reason="Invalid 'any_of' definition in scheme dataset; expected list of options.",
            is_disputed=bool(condition.disputed),
        )

    has_unknown = False
    passed_option_desc = []

    for option in sub_conditions:
        if isinstance(option, dict):
            # Form 1: {'category': '...'}
            if "category" in option:
                cat_val = option["category"]
                # Check profile community, category, or cards
                user_cat, has_cat = profile.get_field_value("category")
                user_comm, has_comm = profile.get_field_value("community")
                user_flag, has_flag = profile.get_field_value(cat_val)

                if has_flag and bool(user_flag):
                    passed_option_desc.append(cat_val)
                    break
                if (has_cat and str(user_cat).strip().lower() == cat_val) or (
                    has_comm and str(user_comm).strip().lower() == cat_val
                ):
                    passed_option_desc.append(cat_val)
                    break
                if not has_cat and not has_comm and not has_flag:
                    has_unknown = True

            # Form 2: {'field': 'annual_family_income_inr', 'op': 'lte', 'value': 800000}
            elif "field" in option:
                sub_field = option["field"]
                sub_op = option.get("op", "eq")
                sub_val = option.get("value")
                actual_val, is_known = profile.get_field_value(sub_field)
                if not is_known:
                    has_unknown = True
                else:
                    op_func = get_operator(sub_op)
                    if op_func:
                        match, _ = op_func(actual_val, sub_val)
                        if match:
                            passed_option_desc.append(f"{sub_field} {sub_op} {sub_val}")
                            break

    if passed_option_desc:
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.PASS,
            actual=passed_option_desc[0],
            expected=condition.value,
            operator="any_of",
            reason=f"Satisfied qualifying condition via '{passed_option_desc[0]}'.",
            is_disputed=bool(condition.disputed),
            note=condition.note,
        )

    if has_unknown:
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.UNKNOWN,
            actual=None,
            expected=condition.value,
            operator="any_of",
            reason=f"Required qualification details for '{condition.field}' are incomplete/unverified.",
            is_disputed=bool(condition.disputed),
            note=condition.note,
        )

    return CriterionResult(
        field=condition.field,
        status=CriterionStatus.FAIL,
        actual=None,
        expected=condition.value,
        operator="any_of",
        reason=f"Did not meet any of the qualifying conditions for '{condition.field}'.",
        is_disputed=bool(condition.disputed),
        note=condition.note,
    )


def evaluate_condition(
    condition: ConditionDefinition, profile: CitizenProfile
) -> CriterionResult:
    """
    Evaluates a single scheme condition against the confirmed citizen profile.
    """
    # 1. Check if condition applies only under certain conditions (applies_only_if)
    if condition.applies_only_if:
        applies, is_known = _check_applies_only_if(condition.applies_only_if, profile)
        if is_known and not applies:
            return CriterionResult(
                field=condition.field,
                status=CriterionStatus.SKIPPED,
                actual=None,
                expected=condition.value,
                operator=condition.op,
                reason=f"Rule skipped because prerequisite clause '{condition.applies_only_if}' does not apply.",
                note=condition.note,
            )
        if not is_known:
            # We don't know whether this rule applies yet
            return CriterionResult(
                field=condition.field,
                status=CriterionStatus.UNKNOWN,
                actual=None,
                expected=condition.value,
                operator=condition.op,
                reason=f"Prerequisite clause '{condition.applies_only_if}' cannot be evaluated (information unknown).",
                note=condition.note,
            )

    # 2. Check scope restrictions (e.g. rural vs urban income caps)
    if condition.scope:
        applies, is_known = _check_scope_applicability(condition.scope, profile)
        if is_known and not applies:
            return CriterionResult(
                field=condition.field,
                status=CriterionStatus.SKIPPED,
                actual=None,
                expected=condition.value,
                operator=condition.op,
                reason=f"Rule skipped: applicant profile does not match rule scope '{condition.scope}'.",
                note=condition.note,
            )
        if not is_known:
            return CriterionResult(
                field=condition.field,
                status=CriterionStatus.UNKNOWN,
                actual=None,
                expected=condition.value,
                operator=condition.op,
                reason=f"Scope '{condition.scope}' cannot be determined without community/residence information.",
                note=condition.note,
            )

    # 3. Disputed condition with null value (cannot be evaluated deterministically)
    if condition.disputed and condition.value is None:
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.UNKNOWN,
            actual=None,
            expected=None,
            operator=condition.op,
            reason=f"Official rule threshold for '{condition.field}' is disputed in government sources; requires manual/official verification.",
            is_disputed=True,
            note=condition.note,
        )

    # 4. Handle compound 'any_of' operator
    if condition.op == "any_of":
        return evaluate_any_of_condition(condition, profile)

    # 5. Extract actual profile value
    actual_val, is_known = profile.get_field_value(condition.field)

    # STRICT UNKNOWN SEMANTICS: UNKNOWN must never default to 0, false, or pass
    if not is_known or actual_val is None:
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.UNKNOWN,
            actual=None,
            expected=condition.value,
            operator=condition.op,
            reason=f"Required eligibility field '{condition.field}' is not provided or unknown.",
            is_disputed=bool(condition.disputed),
            note=condition.note,
        )

    # 6. Lookup operator implementation
    op_func = get_operator(condition.op)
    if not op_func:
        return CriterionResult(
            field=condition.field,
            status=CriterionStatus.FAIL,
            actual=actual_val,
            expected=condition.value,
            operator=condition.op,
            reason=f"Unsupported operator '{condition.op}' configured in scheme rule.",
            is_disputed=bool(condition.disputed),
            note=condition.note,
        )

    # 7. Evaluate operator
    passed, op_detail = op_func(actual_val, condition.value)

    # 8. Handle exception clauses (e.g. Anganwadi worker exception in PMMVY)
    if not passed and condition.exception:
        user_occ, _ = profile.get_field_value("occupation")
        if user_occ and str(user_occ).strip().lower() == condition.exception.strip().lower():
            passed = True
            op_detail = f"Exempted via '{condition.exception}' exception."

    # 9. Handle 'then_requires' clauses (e.g. KCC age > 60 requiring co-borrower)
    if condition.then_requires:
        req_field = condition.then_requires
        if not passed:
            # Trigger condition was not met (e.g. applicant is <= 60), so co-borrower is NOT required
            return CriterionResult(
                field=req_field,
                status=CriterionStatus.SKIPPED,
                actual=actual_val,
                expected=condition.value,
                operator="then_requires",
                reason=f"Requirement '{req_field}' not triggered: applicant {condition.field} ({actual_val}) does not exceed threshold ({condition.value}).",
                note=condition.note,
            )

        # Trigger condition was met (e.g. age > 60), so required field MUST be present and True
        req_val, req_known = profile.get_field_value(req_field)
        if not req_known:
            return CriterionResult(
                field=req_field,
                status=CriterionStatus.UNKNOWN,
                actual=None,
                expected=True,
                operator="then_requires",
                reason=f"Applicant satisfies '{condition.field} {condition.op} {condition.value}', which requires '{req_field}', but this is unknown.",
                note=condition.note,
            )
        if not bool(req_val):
            return CriterionResult(
                field=req_field,
                status=CriterionStatus.FAIL,
                actual=req_val,
                expected=True,
                operator="then_requires",
                reason=f"Condition met for '{condition.field} {condition.op} {condition.value}', but mandatory requirement '{req_field}' is not satisfied.",
                note=condition.note,
            )
        return CriterionResult(
            field=req_field,
            status=CriterionStatus.PASS,
            actual=req_val,
            expected=True,
            operator="then_requires",
            reason=f"Mandatory requirement '{req_field}' is satisfied for applicant with {condition.field} {condition.op} {condition.value}.",
            note=condition.note,
        )

    status = CriterionStatus.PASS if passed else CriterionStatus.FAIL

    if status == CriterionStatus.PASS:
        reason = f"Satisfied: {condition.field} is {actual_val} ({op_detail})."
    else:
        reason = f"Not satisfied: {condition.field} is {actual_val}, but rule requires {condition.op} {condition.value} ({op_detail})."

    return CriterionResult(
        field=condition.field,
        status=status,
        actual=actual_val,
        expected=condition.value,
        operator=condition.op,
        reason=reason,
        is_disputed=bool(condition.disputed),
        note=condition.note,
    )


def evaluate_eligibility(
    profile: Union[CitizenProfile, Dict[str, Any]],
    scheme: Union[SchemeDefinition, Dict[str, Any]],
) -> SchemeEvaluationResult:
    """
    Evaluates a confirmed citizen profile against a single scheme definition.
    Deterministic, rule-based evaluation.
    """
    # Normalize inputs to Pydantic models
    if not isinstance(profile, CitizenProfile):
        profile = CitizenProfile.model_validate(profile)

    if not isinstance(scheme, SchemeDefinition):
        scheme = SchemeDefinition.model_validate(scheme)

    criterion_results: List[CriterionResult] = []

    # 1. State restriction check
    if scheme.state_restriction:
        user_state, state_known = profile.get_field_value("state")
        if not state_known:
            criterion_results.append(
                CriterionResult(
                    field="state",
                    status=CriterionStatus.UNKNOWN,
                    actual=None,
                    expected=scheme.state_restriction,
                    operator="eq",
                    reason=f"Scheme is restricted to {scheme.state_restriction}, but applicant's state is unknown.",
                )
            )
        elif str(user_state).strip().lower() != scheme.state_restriction.strip().lower():
            criterion_results.append(
                CriterionResult(
                    field="state",
                    status=CriterionStatus.FAIL,
                    actual=user_state,
                    expected=scheme.state_restriction,
                    operator="eq",
                    reason=f"Scheme is restricted to {scheme.state_restriction}, but applicant resides in {user_state}.",
                )
            )
        else:
            criterion_results.append(
                CriterionResult(
                    field="state",
                    status=CriterionStatus.PASS,
                    actual=user_state,
                    expected=scheme.state_restriction,
                    operator="eq",
                    reason=f"Applicant resides in eligible state: {user_state}.",
                )
            )

    # 2. Evaluate all configured conditions
    for cond in scheme.eligibility.conditions:
        res = evaluate_condition(cond, profile)
        criterion_results.append(res)

    # 3. Categorize results
    passed = [r for r in criterion_results if r.status == CriterionStatus.PASS]
    failed = [r for r in criterion_results if r.status == CriterionStatus.FAIL]
    unresolved = [r for r in criterion_results if r.status == CriterionStatus.UNKNOWN]

    # 4. Check critical fields
    missing_critical = []
    for crit_field in scheme.eligibility.critical_fields:
        if not profile.is_field_known(crit_field):
            missing_critical.append(crit_field)

    # Collect disputed fields
    disputed_fields = list(scheme.disputed_fields)
    for r in criterion_results:
        if r.is_disputed and r.field not in disputed_fields:
            disputed_fields.append(r.field)

    # 5. Determine scheme outcome
    if len(failed) > 0:
        outcome = SchemeOutcome.NOT_ELIGIBLE
        fail_reasons = "; ".join(f[r.field] for r in failed for f in [{r.field: r.reason}])
        summary = f"Not eligible: {len(failed)} condition(s) failed ({fail_reasons})."
    elif len(unresolved) > 0 or len(missing_critical) > 0:
        outcome = SchemeOutcome.INCOMPLETE_UNKNOWN
        unresolved_names = sorted(list(set([r.field for r in unresolved] + missing_critical)))
        summary = (
            f"Eligibility incomplete: missing or unverified fields: {', '.join(unresolved_names)}."
        )
    else:
        # Check if downstream preparation or readiness is required
        prep_required = getattr(scheme, "preparation_required", False) or getattr(scheme, "requires_preparation", False)
        profile_prep = False
        if hasattr(profile, "get_field_value"):
            val, known = profile.get_field_value("preparation_required")
            if known and val is True:
                profile_prep = True
            prep_schemes, ps_known = profile.get_field_value("preparation_required_schemes")
            if ps_known and isinstance(prep_schemes, list) and scheme.scheme_id in prep_schemes:
                profile_prep = True

        if prep_required or profile_prep:
            outcome = SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED
            summary = f"Actionable: core eligibility satisfied ({len(passed)} criteria passed), preparation/readiness required."
        else:
            outcome = SchemeOutcome.FULLY_ELIGIBLE
            summary = f"Fully eligible: all {len(passed)} evaluated criteria passed."

    return SchemeEvaluationResult(
        scheme_id=scheme.scheme_id,
        scheme_title=scheme.title_en,
        outcome=outcome,
        criterion_results=criterion_results,
        passed_criteria=passed,
        failed_criteria=failed,
        unresolved_criteria=unresolved,
        missing_critical_fields=missing_critical,
        summary_reason=summary,
        disputed_fields=disputed_fields,
    )


def evaluate_all_schemes(
    profile: Union[CitizenProfile, Dict[str, Any]],
    schemes: Optional[List[Union[SchemeDefinition, Dict[str, Any]]]] = None,
) -> MultiSchemeEvaluationResult:
    """
    Evaluates a citizen profile across all provided or configured schemes.
    Does NOT rank schemes or stop after the first match.
    """
    if schemes is None:
        schemes = load_all_schemes()

    evaluations: Dict[str, SchemeEvaluationResult] = {}
    fully_eligible: List[str] = []
    actionable: List[str] = []
    not_eligible: List[str] = []
    incomplete: List[str] = []

    for s in schemes:
        res = evaluate_eligibility(profile, s)
        evaluations[res.scheme_id] = res

        if res.outcome == SchemeOutcome.FULLY_ELIGIBLE:
            fully_eligible.append(res.scheme_id)
        elif res.outcome == SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED:
            actionable.append(res.scheme_id)
        elif res.outcome == SchemeOutcome.NOT_ELIGIBLE:
            not_eligible.append(res.scheme_id)
        else:
            incomplete.append(res.scheme_id)

    return MultiSchemeEvaluationResult(
        total_schemes_evaluated=len(schemes),
        evaluations=evaluations,
        fully_eligible_schemes=fully_eligible,
        actionable_schemes=actionable,
        not_eligible_schemes=not_eligible,
        incomplete_schemes=incomplete,
    )
