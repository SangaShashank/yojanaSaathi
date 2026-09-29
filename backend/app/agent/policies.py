"""
Yojana Saathi - Agent Policies and Action Generation
===================================================
Generates valid candidate actions from state, scores candidate questions,
and provides a deterministic fallback policy for reliable operation.
"""

from typing import Any, Dict, List, Optional
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.state import AgentState
from backend.app.agent.validator import ActionValidator


# Standard natural-language phrasing for missing profile fields
STANDARD_QUESTIONS: Dict[str, str] = {
    "age": "What is your current age?",
    "gender": "What is your gender?",
    "state": "Which state do you currently reside in?",
    "district": "Which district do you reside in?",
    "occupation": "What is your primary occupation or source of livelihood?",
    "occupation_type": "Are you a landowner, tenant farmer, or agricultural worker?",
    "land_ownership": "Do you own cultivable agricultural land?",
    "land_acres": "How many acres of agricultural land do you own or cultivate?",
    "land_holding_acres": "How many acres of agricultural land do you own or cultivate?",
    "land_record_date": "When was your agricultural land record or purchase registered?",
    "farmer_id_status": "Do you have an active registered Farmer ID card with the Agriculture Department?",
    "active_cultivation_status": "Is your agricultural land currently under active cultivation?",
    "cultivates_land": "Do you actively cultivate agricultural land?",
    "land_verification_source": "Is your land record verified on the Bhu Bharati or state revenue portal?",
    "annual_income_inr": "What is your approximate annual family income in rupees?",
    "annual_family_income_inr": "What is your approximate total annual family income?",
    "is_bpl": "Does your family hold a valid BPL (Below Poverty Line) ration card?",
    "category": "Which social or occupational category applies to you?",
    "caste_category": "Which social or caste category do you belong to (e.g., General, OBC, SC, or ST)?",
    "community": "Which social community category do you belong to?",
    "residence_type": "Do you reside in a rural village or an urban area?",
    "farmer_type": "What type of farmer are you, such as small, marginal, or tenant farmer?",
    "is_institutional_landholder": "Do you hold institutional agricultural land?",
    "has_family_pensioner": "Is anyone in your family a retired government pensioner?",
    "cultivates_notified_crop": "Do you cultivate any notified crops for the current agricultural season?",
    "crop_season": "Which crop season are you currently sowing or cultivating (Kharif or Rabi)?",
    "land_or_tenancy_status": "What is your agricultural land tenure status (owner or tenant)?",
    "enrollment_type": "Are you enrolling as a loanee or non-loanee applicant?",
    "groom_age": "What is the age of the bridegroom?",
    "registration_days_after_lmp": "How many days after your LMP was your pregnancy registered?",
    "widow_status": "Are you applying under the widow assistance category?",
    "facing_violence_or_abuse_flag": "Are you seeking emergency protection or crisis support?",
    "girl_child_age": "What is the age of your girl child for the savings account?",
    "existing_ssy_accounts_count": "How many Sukanya Samriddhi accounts have already been opened for your daughters?",
    "co_borrower_legal_heir": "Do you have a co-borrower or legal heir willing to co-sign the Kisan Credit Card application?",
    "marriage_status": "What is the status of the marriage (pending or recently completed)?",
    "delivery_location_type": "Was the delivery at a government hospital/PHC or a private hospital?",
    "pregnancy_or_lactation_status": "Are you currently pregnant or a lactating mother?",
}

# Domain-specific priority order for missing field intake
FIELD_PRIORITY: List[str] = [
    "state",
    "occupation",
    "occupation_type",
    "age",
    "gender",
    "land_ownership",
    "land_acres",
    "land_record_date",
    "active_cultivation_status",
    "cultivates_land",
    "farmer_id_status",
    "annual_income_inr",
    "annual_family_income_inr",
    "is_bpl",
    "category",
]


def score_missing_field(field_name: str, state: AgentState) -> float:
    """
    Scores a candidate missing field based on candidate scheme narrowing value,
    active scheme priority, domain priority, and penalizes repeated queries.
    """
    base_score = 1.0

    # Scheme-specific boost: if an active scheme needs this field
    if state.active_scheme_id:
        active_missing = state.scheme_missing_information.get(state.active_scheme_id, [])
        if field_name in active_missing:
            base_score += 10.0

    # Narrowing value: how many candidate schemes check this field
    narrowing_hits = sum(
        1 for cond in state.unresolved_conditions if cond.get("field") == field_name
    )
    base_score += narrowing_hits * 2.0

    # Domain priority score
    if field_name in FIELD_PRIORITY:
        priority_boost = (len(FIELD_PRIORITY) - FIELD_PRIORITY.index(field_name)) * 0.1
        base_score += priority_boost

    # Repetition penalty
    if field_name in state.asked_questions:
        base_score -= 5.0

    return base_score


def generate_valid_actions(state: AgentState) -> List[AgentAction]:
    """
    Deterministic generation of all currently valid candidate actions from state.
    """
    actions: List[AgentAction] = []

    # 1. Contradiction Resolution has highest priority
    unresolved_contradictions = [c for c in state.contradictions if not c.resolved]
    if len(unresolved_contradictions) > 0:
        c = unresolved_contradictions[0]
        action = AgentAction(
            action=ActionType.RESOLVE_CONTRADICTION,
            field=c.field,
            question=f"We noted conflicting values for '{c.field}' ({c.existing_value} vs {c.conflicting_value}). Which is accurate?",
            reason_code=ReasonCode.RESOLVE_CONTRADICTION,
            notes=f"Reconcile contradiction on {c.field}",
        )
        if ActionValidator.validate(action, state)[0]:
            actions.append(action)
        return actions  # Must resolve contradiction before other actions

    # Guard: If an actionable selected scheme has no missing eligibility-critical information,
    # do NOT reopen general profile questioning.
    actionable_selected_has_no_missing = False
    if state.selected_schemes and state.scheme_evaluations:
        all_selected_clean = True
        for s_id in state.selected_schemes:
            eval_info = state.scheme_evaluations.get(s_id)
            if not eval_info:
                all_selected_clean = False
                break
            outcome = eval_info.get("outcome")
            s_missing = state.scheme_missing_information.get(s_id, [])
            if outcome not in ["ACTIONABLE_PREPARATION_REQUIRED", "FULLY_ELIGIBLE"] or s_missing:
                all_selected_clean = False
                break
        if all_selected_clean:
            actionable_selected_has_no_missing = True

    # 2. Information Gathering: Generate candidate questions for missing information
    if len(state.missing_information) > 0 and not actionable_selected_has_no_missing:
        # Sort fields by score and deterministic tiebreaker
        scored_fields = []
        for field in state.missing_information:
            score = score_missing_field(field, state)
            scored_fields.append((score, field))

        # Tiebreaker: (-score, priority_rank, alphabetical)
        scored_fields.sort(
            key=lambda x: (
                -x[0],
                FIELD_PRIORITY.index(x[1]) if x[1] in FIELD_PRIORITY else 999,
                x[1],
            )
        )

        for score, field in scored_fields:
            question_text = STANDARD_QUESTIONS.get(
                field, f"Please provide information regarding your {field.replace('_', ' ')}."
            )
            action = AgentAction(
                action=ActionType.ASK_QUESTION,
                field=field,
                question=question_text,
                reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
                notes=f"Field score: {score:.2f}",
            )
            is_valid, _ = ActionValidator.validate(action, state)
            if is_valid:
                actions.append(action)

    # 3. Eligibility Ready / Reevaluation: When missing information is resolved or reevaluation is needed
    current_fp = state.get_profile_fingerprint()
    is_stale = state.evaluated_profile_fingerprint and state.evaluated_profile_fingerprint != current_fp

    if is_stale and not state.pending_confirmation:
        action_reeval = AgentAction(
            action=ActionType.REEVALUATE_SCHEMES,
            reason_code=ReasonCode.PROFILE_REEVALUATION_REQUIRED,
            notes="Confirmed profile has updated; reevaluate affected schemes",
        )
        if ActionValidator.validate(action_reeval, state)[0]:
            actions.append(action_reeval)

    if (
        len(state.missing_information) == 0
        and (len(state.candidate_schemes) > 0 or len(state.evaluated_schemes) == 0)
        and state.stage != "ELIGIBILITY_EVALUATED"
        and len(state.eligible_schemes) == 0
        and len(state.eliminated_schemes) == 0
        and not state.pending_confirmation
        and len(state.selected_schemes) == 0
        and len(state.applications) == 0
    ):
        run_elig_action = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
            notes="All eligibility-critical fields are available; trigger deterministic engine",
        )
        if ActionValidator.validate(run_elig_action, state)[0]:
            actions.append(run_elig_action)

        action = AgentAction(
            action=ActionType.EVALUATE_SCHEMES,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
            notes="All eligibility-critical fields are available; trigger multi-scheme deterministic engine",
        )
        if ActionValidator.validate(action, state)[0]:
            actions.append(action)

    # 4. Document and Readiness Actions (when applications exist or document workflow is active)
    active_app_id = state.active_application_id
    if not active_app_id and state.applications:
        active_app_id = next(iter(state.applications.values())).get("id") if isinstance(next(iter(state.applications.values())), dict) else next(iter(state.applications.keys()))

    if active_app_id:
        from backend.app.services.document_coordinator import DocumentCoordinator
        from backend.app.schemas.document import DocumentRequirementStatus, ReadinessStatus
        coord = DocumentCoordinator()
        checklist = coord.get_application_checklist(state, active_app_id)

        # 4a. Check for open discrepancies on active application
        open_discs = []
        docs_list = []
        if hasattr(state, "documents"):
            if isinstance(state.documents, dict):
                docs_list = state.documents.get(active_app_id, [])
            elif isinstance(state.documents, list):
                docs_list = [d for d in state.documents if isinstance(d, dict) and d.get("application_id") == active_app_id]

        for d in docs_list:
            for disc in d.get("discrepancies", []):
                if disc.get("status") == "OPEN":
                    open_discs.append(disc)

        if open_discs:
            d_item = open_discs[0]
            disc_action = AgentAction(
                action=ActionType.RESOLVE_DOCUMENT_DISCREPANCY,
                field=d_item.get("discrepancy_id"),
                arguments={
                    "discrepancy_id": d_item.get("discrepancy_id"),
                    "resolution": "KEEP_PROFILE",
                },
                reason_code=ReasonCode.DOCUMENT_DISCREPANCY_DETECTED,
                notes=f"Resolve factual discrepancy on field '{d_item.get('field_name')}'",
            )
            if ActionValidator.validate(disc_action, state)[0]:
                actions.append(disc_action)

        # 4b. Check for uploaded documents pending processing
        pending_docs = [
            d for d in docs_list
            if d.get("status") in ["UPLOADED", "PENDING"] and d.get("extraction_status") == "PENDING"
        ]

        if pending_docs:
            p_doc = pending_docs[0]
            proc_action = AgentAction(
                action=ActionType.PROCESS_DOCUMENT,
                field=p_doc.get("id"),
                arguments={"document_id": p_doc.get("id"), "application_id": active_app_id},
                reason_code=ReasonCode.DOCUMENT_PENDING_PROCESSING,
                notes=f"Process uploaded document {p_doc.get('document_type')}",
            )
            if ActionValidator.validate(proc_action, state)[0]:
                actions.append(proc_action)


        # 4c. Check for missing mandatory documents
        missing_reqs = [
            r for r in checklist
            if r.required and r.status in [DocumentRequirementStatus.REQUIRED.value, DocumentRequirementStatus.INVALID.value]
        ]
        if missing_reqs and not pending_docs and not open_discs:
            m_req = missing_reqs[0]
            req_action = AgentAction(
                action=ActionType.REQUEST_DOCUMENT,
                field=m_req.document_type,
                arguments={"document_type": m_req.document_type, "application_id": active_app_id},
                question=f"Please upload your {m_req.name} to complete application readiness.",
                reason_code=ReasonCode.DOCUMENT_REQUIRED,
                notes=f"Mandatory requirement {m_req.requirement_id} is missing",
            )
            if ActionValidator.validate(req_action, state)[0]:
                actions.append(req_action)

        # 4d. Readiness check / Ready for Handoff
        verified_count = sum(1 for r in checklist if r.status == DocumentRequirementStatus.VERIFIED.value)
        total_mandatory = sum(1 for r in checklist if r.required and r.status != DocumentRequirementStatus.NOT_REQUIRED.value)
        if total_mandatory > 0 and verified_count == total_mandatory and not open_discs:
            ready_action = AgentAction(
                action=ActionType.READY_FOR_HANDOFF,
                field=active_app_id,
                arguments={"application_id": active_app_id},
                reason_code=ReasonCode.ALL_DOCUMENTS_VERIFIED,
                notes="All mandatory documents verified; application is ready for handoff",
            )
            if ActionValidator.validate(ready_action, state)[0]:
                actions.append(ready_action)

        # Phase 6 remains state-driven: only a handoff-ready track may be verified
        # or offered package generation. The dispatcher re-verifies before writing.
        if state.stage == "READY_FOR_HANDOFF" or any(a.get("status") == "READY_FOR_HANDOFF" for a in state.applications.values()):
            verify_action = AgentAction(
                action=ActionType.VERIFY_PRE_SUBMISSION,
                field=active_app_id,
                arguments={"application_id": active_app_id},
                reason_code=ReasonCode.PRE_SUBMISSION_VERIFICATION_REQUIRED,
                notes="Verify current profile, eligibility, documents, and readiness before CSC/VLE handoff",
            )
            if ActionValidator.validate(verify_action, state)[0]:
                actions.append(verify_action)
            package_action = AgentAction(
                action=ActionType.GENERATE_HANDOFF_PACKAGE,
                field=active_app_id,
                arguments={"application_id": active_app_id},
                reason_code=ReasonCode.HANDOFF_PACKAGE_READY,
                notes="Generate the non-official preparation package only after verification",
            )
            if ActionValidator.validate(package_action, state)[0]:
                actions.append(package_action)

        # 4e. Phase 7: Application Rejection Recovery Actions
        app_dict = state.applications.get(active_app_id) or {}
        app_status = app_dict.get("status")
        if app_status == "REJECTION_EVIDENCE_REQUIRED":
            rej_action = AgentAction(
                action=ActionType.REQUEST_REJECTION_EVIDENCE,
                field=active_app_id,
                arguments={"application_id": active_app_id},
                question="Please provide your official rejection notice, letter, or SMS to diagnose the rejection reason.",
                reason_code=ReasonCode.REJECTION_EVIDENCE_REQUIRED,
                notes="Citizen indicated rejection; official evidence required before diagnosing",
            )
            if ActionValidator.validate(rej_action, state)[0]:
                actions.append(rej_action)

        elif app_status in ("RECOVERY_REQUIRED", "RECOVERY_IN_PROGRESS"):
            rec_action = AgentAction(
                action=ActionType.REQUEST_RECOVERY_DOCUMENT,
                field=active_app_id,
                arguments={"application_id": active_app_id, "rejection_event_id": app_dict.get("rejection_event_id") or "event_current"},
                question="Please upload the updated bank proof or correction document to complete recovery.",
                reason_code=ReasonCode.RECOVERY_REQUIRED,
                notes="Rejection diagnosed; requesting remediation document",
            )
            if ActionValidator.validate(rec_action, state)[0]:
                actions.append(rec_action)

    # 5. Multi-scheme application switching if multiple applications exist
    if len(state.applications) > 1 and state.active_scheme_id:
        other_schemes = [s for s in state.applications.keys() if s != state.active_scheme_id]
        if other_schemes:
            switch_action = AgentAction(
                action=ActionType.SWITCH_ACTIVE_APPLICATION,
                field=other_schemes[0],
                arguments={"scheme_id": other_schemes[0]},
                reason_code=ReasonCode.ACTIVE_APPLICATION_SWITCHED,
                notes=f"Switch active context to scheme track {other_schemes[0]}",
            )
            if ActionValidator.validate(switch_action, state)[0]:
                actions.append(switch_action)

    # 6. Finish: Objective complete (eligibility evaluated with eligible schemes, or terminal)
    if len(state.eligible_schemes) > 0 or state.stage in ["ELIGIBILITY_EVALUATED", "READY_FOR_HANDOFF"]:
        action = AgentAction(
            action=ActionType.FINISH,
            reason_code=ReasonCode.TERMINAL_STATE,
            notes="Eligibility evaluation completed and results recorded",
        )
        if ActionValidator.validate(action, state)[0]:
            actions.append(action)

    # 7. No Supported Match: Candidates evaluated, zero eligible/actionable
    has_evaluated = len(state.eliminated_schemes) > 0 or len(state.evaluated_schemes) > 0
    if (
        (len(state.candidate_schemes) == 0 and len(state.eligible_schemes) == 0)
        or (has_evaluated and len(state.eligible_schemes) == 0 and len(state.missing_information) == 0)
    ):
        action = AgentAction(
            action=ActionType.NO_SUPPORTED_MATCH,
            reason_code=ReasonCode.NO_SUPPORTED_MATCH,
            notes="No configured government scheme matches the confirmed profile",
        )
        if ActionValidator.validate(action, state)[0]:
            actions.append(action)

    # 8. Escalate Human: Safe fallback if no progress is possible
    escalate_action = AgentAction(
        action=ActionType.ESCALATE_HUMAN,
        reason_code=ReasonCode.HUMAN_VERIFICATION_REQUIRED,
        notes="Escalate case to CSC operator or human counselor",
    )
    actions.append(escalate_action)

    return actions



class DeterministicPolicy:
    """
    Baseline deterministic policy that selects the best valid next action based on state.
    Used directly in offline/test scenarios and as a robust fallback for Gemini proposals.
    """

    @classmethod
    def select_action(cls, state: AgentState) -> AgentAction:
        valid_actions = generate_valid_actions(state)

        # 1. Contradiction takes immediate priority
        for act in valid_actions:
            if act.action == ActionType.RESOLVE_CONTRADICTION:
                return act

        # 2. Missing information -> ASK_QUESTION with top score
        for act in valid_actions:
            if act.action == ActionType.ASK_QUESTION:
                return act

        # 3. Complete profile -> RUN_ELIGIBILITY (or EVALUATE_SCHEMES)
        for act in valid_actions:
            if act.action == ActionType.RUN_ELIGIBILITY:
                return act
        for act in valid_actions:
            if act.action == ActionType.EVALUATE_SCHEMES:
                return act

        # 3b. Reevaluate schemes if stale
        for act in valid_actions:
            if act.action == ActionType.REEVALUATE_SCHEMES:
                return act

        # 3c. Document and Readiness Actions (Discrepancy -> Process -> Recovery -> Request -> Ready)
        for act in valid_actions:
            if act.action == ActionType.RESOLVE_DOCUMENT_DISCREPANCY:
                return act
        for act in valid_actions:
            if act.action == ActionType.PROCESS_DOCUMENT:
                return act
        # 3d. Rejection and Recovery Actions take precedence over regular intake
        for act in valid_actions:
            if act.action in (
                ActionType.REQUEST_REJECTION_EVIDENCE,
                ActionType.DECODE_REJECTION,
                ActionType.REQUEST_RECOVERY_DOCUMENT,
                ActionType.RESOLVE_REJECTION,
                ActionType.REASSESS_APPLICATION,
            ):
                return act
        for act in valid_actions:
            if act.action == ActionType.REQUEST_DOCUMENT:
                return act
        for act in valid_actions:
            if act.action == ActionType.READY_FOR_HANDOFF:
                return act
        for act in valid_actions:
            if act.action == ActionType.VERIFY_PRE_SUBMISSION:
                return act
        for act in valid_actions:
            if act.action == ActionType.GENERATE_HANDOFF_PACKAGE:
                return act
        for act in valid_actions:
            if act.action == ActionType.CALCULATE_READINESS:
                return act

        # 4. Finish (when eligibility complete and no pending document action)
        for act in valid_actions:
            if act.action == ActionType.FINISH:
                return act


        # 5. No supported match
        for act in valid_actions:
            if act.action == ActionType.NO_SUPPORTED_MATCH:
                return act

        # 6. Fallback escalation
        return AgentAction(
            action=ActionType.ESCALATE_HUMAN,
            reason_code=ReasonCode.HUMAN_VERIFICATION_REQUIRED,
            notes="Deterministic fallback escalation",
        )
