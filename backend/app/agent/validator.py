"""
Yojana Saathi - Action Validator
================================
Validates proposed AgentActions against current AgentState before execution.
Guarantees bounded autonomy and prevents LLM hallucinations from executing invalid actions.
"""

from typing import Optional, Tuple
from backend.app.agent.actions import ActionType, AgentAction
from backend.app.agent.state import AgentState


class ActionValidator:
    """
    Deterministic validator enforcing system contracts on proposed actions.
    """

    @classmethod
    def validate(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        """
        Validates an action against state.
        
        Returns:
            (is_valid, error_message):
            - If valid: (True, None)
            - If invalid: (False, "Explanation of contract violation")
        """
        if not isinstance(action, AgentAction):
            return False, f"Proposed action must be an AgentAction instance, got {type(action).__name__}"

        # Cannot execute actions after state is already terminated
        if state.is_terminated and action.action != ActionType.FINISH:
            return False, "Agent state is already terminated; only FINISH is permitted."

        validator_method = getattr(cls, f"_validate_{action.action.value.lower()}", None)
        if not validator_method:
            return False, f"No validator implemented for action type: {action.action.value}"

        return validator_method(action, state)

    @classmethod
    def _validate_ask_question(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        if not action.field:
            return False, "ASK_QUESTION requires a target 'field' parameter."

        if not action.question or not action.question.strip():
            return False, "ASK_QUESTION requires a non-empty 'question' string."

        # Rule: Cannot ask for a field that is already confirmed and known
        if action.field in state.profile and state.profile[action.field] not in [None, "UNKNOWN", "unknown"]:
            if action.field not in state.uncertain_fields:
                return False, f"Field '{action.field}' is already known and confirmed; redundant questions are forbidden."

        # Rule: Field must be in missing_information or relevant to candidate schemes
        is_missing = action.field in state.missing_information
        is_unresolved = any(
            cond.get("field") == action.field for cond in state.unresolved_conditions
        )
        if not is_missing and not is_unresolved and len(state.missing_information) > 0:
            return False, f"Field '{action.field}' is not in current missing_information list: {state.missing_information}"

        # Repeated-question guard: Cannot re-ask the exact same field if it was just asked without answer
        if state.last_action and state.last_action.action == ActionType.ASK_QUESTION:
            if state.last_action.field == action.field:
                val = state.profile.get(action.field)
                if val is None or val in ["UNKNOWN", "unknown"]:
                    return False, f"Repeated question guard: '{action.field}' was just asked and has not been answered."

        return True, None

    @classmethod
    def _validate_run_eligibility(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        # Rule: Cannot re-run eligibility if already evaluated on current state
        if state.stage == "ELIGIBILITY_EVALUATED" and (len(state.eligible_schemes) > 0 or len(state.eliminated_schemes) > 0):
            return False, "Eligibility has already been evaluated for the current profile state."

        # Rule: Profile changes pending confirmation must be confirmed or rejected first
        if state.pending_confirmation:
            return False, "Cannot RUN_ELIGIBILITY while profile changes are pending human confirmation."

        # Rule: Unresolved contradictions must be resolved before evaluating eligibility
        active_contradictions = [c for c in state.contradictions if not c.resolved]
        if len(active_contradictions) > 0:
            return False, f"Cannot RUN_ELIGIBILITY while {len(active_contradictions)} unresolved contradiction(s) exist."

        # Rule: Cannot run eligibility if candidate set is empty
        if len(state.candidate_schemes) == 0 and len(state.eligible_schemes) == 0:
            return False, "Cannot RUN_ELIGIBILITY: candidate schemes list is empty."

        # Rule: Critical missing information must be gathered first
        if len(state.missing_information) > 0:
            return False, (
                f"Cannot RUN_ELIGIBILITY: profile is incomplete. "
                f"Missing critical fields: {state.missing_information}"
            )

        return True, None

    @classmethod
    def _validate_evaluate_schemes(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        if state.pending_confirmation:
            return False, "Cannot EVALUATE_SCHEMES while profile changes are pending human confirmation."

        active_contradictions = [c for c in state.contradictions if not c.resolved]
        if len(active_contradictions) > 0:
            return False, f"Cannot EVALUATE_SCHEMES while {len(active_contradictions)} unresolved contradiction(s) exist."

        return True, None

    @classmethod
    def _validate_select_schemes(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        selected_ids = action.arguments.get("selected_scheme_ids")
        if not selected_ids or not isinstance(selected_ids, list):
            return False, "SELECT_SCHEMES requires a non-empty list 'selected_scheme_ids' in arguments."

        if len(selected_ids) != len(set(selected_ids)):
            return False, "SELECT_SCHEMES cannot contain duplicate scheme IDs."

        # Verify all selected schemes have been evaluated
        current_fp = state.get_profile_fingerprint()
        for s_id in selected_ids:
            eval_data = state.scheme_evaluations.get(s_id)
            if not eval_data:
                return False, f"Scheme '{s_id}' has not been evaluated."
            if eval_data.get("profile_fingerprint") != current_fp:
                return False, f"Scheme '{s_id}' evaluation is stale; reevaluation required."
            outcome = eval_data.get("outcome")
            if outcome not in ["FULLY_ELIGIBLE", "ACTIONABLE_PREPARATION_REQUIRED"]:
                return False, f"Scheme '{s_id}' outcome is '{outcome}'; only eligible/actionable schemes can be selected."

        return True, None

    @classmethod
    def _validate_create_applications(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        return cls._validate_select_schemes(action, state)

    @classmethod
    def _validate_switch_active_application(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        target = action.field or action.arguments.get("scheme_id") or action.arguments.get("application_id")
        if not target:
            return False, "SWITCH_ACTIVE_APPLICATION requires a target 'scheme_id' or 'application_id'."
        if target not in state.applications:
            matching_app = any(app.get("id") == target for app in state.applications.values())
            if not matching_app:
                return False, f"Target '{target}' is not an active application in this case."
        return True, None

    @classmethod
    def _validate_reevaluate_schemes(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        if state.pending_confirmation:
            return False, "Cannot REEVALUATE_SCHEMES while profile changes are pending human confirmation."
        return True, None

    @classmethod
    def _validate_resolve_contradiction(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        active_contradictions = [c for c in state.contradictions if not c.resolved]
        if len(active_contradictions) == 0:
            return False, "RESOLVE_CONTRADICTION is only valid when unresolved contradictions exist in state."
        return True, None

    @classmethod
    def _validate_no_supported_match(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        # If candidate schemes still exist and have not been evaluated, we cannot claim no match
        if len(state.candidate_schemes) > 0 and len(state.eligible_schemes) == 0 and len(state.eliminated_schemes) == 0:
            # Candidates exist but haven't been evaluated
            if len(state.missing_information) > 0:
                return False, "Cannot conclude NO_SUPPORTED_MATCH while candidate schemes remain unevaluated."

        # If eligible schemes were found, NO_SUPPORTED_MATCH is invalid
        if len(state.eligible_schemes) > 0:
            return False, f"Cannot declare NO_SUPPORTED_MATCH: found {len(state.eligible_schemes)} eligible scheme(s)."

        return True, None

    @classmethod
    def _validate_finish(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        # Valid if eligibility evaluation completed or terminal state reached or no actionable info
        eligibility_done = len(state.eligible_schemes) > 0 or len(state.eliminated_schemes) > 0
        no_actionable_info = len(state.missing_information) == 0 and len(state.candidate_schemes) == 0

        if not eligibility_done and not no_actionable_info and not state.is_terminated:
            if len(state.missing_information) > 0:
                return False, f"Cannot FINISH prematurely: missing information remains {state.missing_information}"

        return True, None

    @classmethod
    def _validate_escalate_human(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        # ESCALATE_HUMAN is always a safe escape hatch when safety or progress is blocked
        return True, None

    @classmethod
    def _validate_reevaluate_candidates(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        return True, None

    @classmethod
    def _validate_request_clarification(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        if not action.question or not action.question.strip():
            return False, "REQUEST_CLARIFICATION requires a non-empty question."
        return True, None

    @classmethod
    def _validate_request_document(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        app_id = action.arguments.get("application_id") or state.active_application_id
        if not app_id and not state.applications:
            return False, "REQUEST_DOCUMENT requires an active application or configured applications."
        doc_type = action.field or action.arguments.get("document_type")
        if not doc_type:
            return False, "REQUEST_DOCUMENT requires a target 'field' or 'document_type' specifying the document."
        return True, None

    @classmethod
    def _validate_process_document(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        doc_id = action.field or action.arguments.get("document_id")
        if not doc_id:
            return False, "PROCESS_DOCUMENT requires a target 'document_id'."
        return True, None

    @classmethod
    def _validate_verify_document(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        doc_id = action.field or action.arguments.get("document_id")
        if not doc_id:
            return False, "VERIFY_DOCUMENT requires a target 'document_id'."
        return True, None

    @classmethod
    def _validate_resolve_document_discrepancy(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        disc_id = action.field or action.arguments.get("discrepancy_id")
        if not disc_id:
            return False, "RESOLVE_DOCUMENT_DISCREPANCY requires a target 'discrepancy_id'."
        res = action.arguments.get("resolution")
        if res and res not in ["KEEP_PROFILE", "USE_DOCUMENT", "ESCALATE"]:
            return False, f"Invalid resolution '{res}'; must be KEEP_PROFILE, USE_DOCUMENT, or ESCALATE."
        return True, None

    @classmethod
    def _validate_calculate_readiness(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        app_id = action.field or action.arguments.get("application_id") or state.active_application_id
        if not app_id and not state.applications:
            return False, "CALCULATE_READINESS requires an application to evaluate."
        return True, None

    @classmethod
    def _validate_ready_for_handoff(cls, action: AgentAction, state: AgentState) -> Tuple[bool, Optional[str]]:
        app_id = action.field or action.arguments.get("application_id") or state.active_application_id
        if not app_id and not state.applications:
            return False, "READY_FOR_HANDOFF requires an active application."
        return True, None

