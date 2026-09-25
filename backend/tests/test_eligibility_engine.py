"""
Unit Tests for Deterministic Eligibility Engine
===============================================
Verifies:
- All rules passing -> FULLY_ELIGIBLE
- One or multiple rules failing -> NOT_ELIGIBLE
- UNKNOWN semantics: never defaults to 0, False, empty or PASS
- Missing critical fields -> INCOMPLETE / UNKNOWN
- Boundary values (gt vs gte, lt vs lte)
- Operator edge cases (in, not_in)
- Condition extensions (applies_only_if, then_requires, scope, disputed null values)
"""

import pytest
from backend.app.schemas.profile import CitizenProfile
from backend.app.schemas.scheme import ConditionDefinition, EligibilityDefinition, SchemeDefinition
from backend.app.schemas.eligibility import CriterionStatus, SchemeOutcome
from backend.app.services.eligibility_engine import (
    evaluate_condition,
    evaluate_eligibility,
    evaluate_all_schemes,
)


@pytest.fixture
def sample_test_scheme() -> SchemeDefinition:
    """Fixture providing a synthetic test scheme with varied conditions."""
    return SchemeDefinition(
        scheme_id="test_scheme_001",
        schema_version="2.0",
        niche="farmers",
        title_en="Test Agricultural Support Scheme",
        ministry="Ministry of Agriculture",
        target_audience=["farmer"],
        state_restriction="Telangana",
        eligibility=EligibilityDefinition(
            critical_fields=["age", "land_acres", "occupation", "farmer_id_status"],
            conditions=[
                ConditionDefinition(field="age", op="gte", value=18),
                ConditionDefinition(field="land_acres", op="lte", value=5.0),
                ConditionDefinition(
                    field="occupation",
                    op="not_in",
                    value=["income_tax_payer", "govt_employee"],
                ),
                ConditionDefinition(field="farmer_id_status", op="eq", value="registered"),
            ],
        ),
    )


class TestDeterministicEligibilityEngine:
    def test_all_rules_passing(self, sample_test_scheme):
        profile = CitizenProfile(
            state="Telangana",
            age=35,
            land_acres=3.5,
            occupation="farmer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.FULLY_ELIGIBLE
        assert len(result.failed_criteria) == 0
        assert len(result.unresolved_criteria) == 0
        assert len(result.passed_criteria) == 5  # state + 4 conditions

    def test_one_rule_failing(self, sample_test_scheme):
        # Age 16 (below minimum 18)
        profile = CitizenProfile(
            state="Telangana",
            age=16,
            land_acres=3.5,
            occupation="farmer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        assert len(result.failed_criteria) == 1
        assert result.failed_criteria[0].field == "age"
        assert result.failed_criteria[0].status == CriterionStatus.FAIL

    def test_multiple_rules_failing(self, sample_test_scheme):
        # Wrong state, land > 5, disqualified occupation
        profile = CitizenProfile(
            state="Karnataka",
            age=40,
            land_acres=10.0,
            occupation="income_tax_payer",
            farmer_id_status="registered",
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        assert len(result.failed_criteria) == 3
        failed_fields = [c.field for c in result.failed_criteria]
        assert "state" in failed_fields
        assert "land_acres" in failed_fields
        assert "occupation" in failed_fields

    def test_unknown_semantics_missing_field(self, sample_test_scheme):
        """
        STRICT UNKNOWN SEMANTICS:
        If farmer_id_status is not provided, it must be UNKNOWN, NOT FAIL,
        and the outcome must be INCOMPLETE / UNKNOWN.
        """
        profile = CitizenProfile(
            state="Telangana",
            age=35,
            land_acres=3.5,
            occupation="farmer",
            # farmer_id_status omitted
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.INCOMPLETE_UNKNOWN
        assert len(result.failed_criteria) == 0
        assert len(result.unresolved_criteria) == 1
        assert result.unresolved_criteria[0].field == "farmer_id_status"
        assert result.unresolved_criteria[0].status == CriterionStatus.UNKNOWN

    def test_unknown_semantics_explicit_unknown_string(self, sample_test_scheme):
        """Field passed explicitly as 'UNKNOWN' must evaluate to CriterionStatus.UNKNOWN."""
        profile = CitizenProfile(
            state="Telangana",
            age=35,
            land_acres=3.5,
            occupation="farmer",
            farmer_id_status="UNKNOWN",
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.INCOMPLETE_UNKNOWN
        assert result.unresolved_criteria[0].field == "farmer_id_status"
        assert result.unresolved_criteria[0].status == CriterionStatus.UNKNOWN

    def test_unknown_does_not_mask_explicit_failure(self, sample_test_scheme):
        """
        If one rule fails (e.g. land is 10 acres > 5.0), the outcome is NOT_ELIGIBLE,
        even if another rule is UNKNOWN.
        """
        profile = CitizenProfile(
            state="Telangana",
            age=35,
            land_acres=10.0,  # Fails!
            occupation="farmer",
            # farmer_id_status is UNKNOWN
        )
        result = evaluate_eligibility(profile, sample_test_scheme)

        assert result.outcome == SchemeOutcome.NOT_ELIGIBLE
        assert any(c.field == "land_acres" and c.status == CriterionStatus.FAIL for c in result.failed_criteria)
        assert any(c.field == "farmer_id_status" and c.status == CriterionStatus.UNKNOWN for c in result.unresolved_criteria)

    def test_boundary_values(self):
        cond_gte = ConditionDefinition(field="age", op="gte", value=18)
        cond_gt = ConditionDefinition(field="age", op="gt", value=18)
        cond_lte = ConditionDefinition(field="land_acres", op="lte", value=5.0)
        cond_lt = ConditionDefinition(field="land_acres", op="lt", value=5.0)

        # Exact boundary 18
        p18 = CitizenProfile(age=18, land_acres=5.0)
        assert evaluate_condition(cond_gte, p18).status == CriterionStatus.PASS
        assert evaluate_condition(cond_gt, p18).status == CriterionStatus.FAIL

        # Exact boundary 5.0
        assert evaluate_condition(cond_lte, p18).status == CriterionStatus.PASS
        assert evaluate_condition(cond_lt, p18).status == CriterionStatus.FAIL

        # Below and above boundaries
        p_below = CitizenProfile(age=17, land_acres=4.9)
        assert evaluate_condition(cond_gte, p_below).status == CriterionStatus.FAIL
        assert evaluate_condition(cond_lte, p_below).status == CriterionStatus.PASS

        p_above = CitizenProfile(age=19, land_acres=5.1)
        assert evaluate_condition(cond_gte, p_above).status == CriterionStatus.PASS
        assert evaluate_condition(cond_lte, p_above).status == CriterionStatus.FAIL


class TestConditionExtensions:
    def test_then_requires_condition_satisfied(self):
        """KCC scheme style: age > 60 then_requires co_borrower_legal_heir."""
        cond = ConditionDefinition(
            field="age",
            op="gt",
            value=60,
            then_requires="co_borrower_legal_heir",
        )
        # Case A: Applicant > 60 with co-borrower
        p_with_coborrower = CitizenProfile(age=65, co_borrower_legal_heir=True)
        res = evaluate_condition(cond, p_with_coborrower)
        assert res.status == CriterionStatus.PASS

        # Case B: Applicant > 60 without co-borrower
        p_no_coborrower = CitizenProfile(age=65, co_borrower_legal_heir=False)
        res = evaluate_condition(cond, p_no_coborrower)
        assert res.status == CriterionStatus.FAIL

        # Case C: Applicant > 60 with unknown co-borrower
        p_unknown = CitizenProfile(age=65)
        res = evaluate_condition(cond, p_unknown)
        assert res.status == CriterionStatus.UNKNOWN

        # Case D: Applicant <= 60 (co-borrower requirement does not trigger -> SKIPPED)
        p_young = CitizenProfile(age=45)
        res = evaluate_condition(cond, p_young)
        assert res.status == CriterionStatus.SKIPPED

    def test_applies_only_if_clause(self):
        """Condition applies only if category == widow."""
        cond = ConditionDefinition(
            field="widow_status",
            op="eq",
            value=True,
            applies_only_if="category == widow",
        )
        # Case A: Applicant is widow -> condition applies and evaluates
        p_widow = CitizenProfile(category="widow", widow_status=True)
        assert evaluate_condition(cond, p_widow).status == CriterionStatus.PASS

        # Case B: Applicant is senior citizen -> condition is SKIPPED
        p_senior = CitizenProfile(category="senior_citizen_57_plus")
        assert evaluate_condition(cond, p_senior).status == CriterionStatus.SKIPPED

        # Case C: Applicant category unknown -> condition is UNKNOWN
        p_unknown = CitizenProfile()
        assert evaluate_condition(cond, p_unknown).status == CriterionStatus.UNKNOWN

    def test_disputed_condition_with_null_value(self):
        """Disputed condition where official threshold is null cannot be evaluated deterministically."""
        cond = ConditionDefinition(
            field="application_days_after_marriage",
            op="lte",
            value=None,
            disputed=True,
            conflicting_values_months=[3, 6],
        )
        profile = CitizenProfile(application_days_after_marriage=90)
        res = evaluate_condition(cond, profile)

        assert res.status == CriterionStatus.UNKNOWN
        assert res.is_disputed is True
        assert "disputed" in res.reason.lower()

    def test_compound_any_of_operator(self):
        """PMMVY income qualifying condition with multiple acceptable qualifiers."""
        cond = ConditionDefinition(
            field="income_qualifying_condition",
            op="any_of",
            value=[
                {"category": "sc_st"},
                {"category": "bpl_ration_card"},
                {"field": "annual_family_income_inr", "op": "lte", "value": 800000},
            ],
        )
        # Passing via BPL
        p_bpl = CitizenProfile(bpl_ration_card=True)
        assert evaluate_condition(cond, p_bpl).status == CriterionStatus.PASS

        # Passing via income <= 800000
        p_income = CitizenProfile(annual_family_income_inr=450000)
        assert evaluate_condition(cond, p_income).status == CriterionStatus.PASS

        # Incomplete when no qualifiers provided
        p_empty = CitizenProfile()
        assert evaluate_condition(cond, p_empty).status == CriterionStatus.UNKNOWN
