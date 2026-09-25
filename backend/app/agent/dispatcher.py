"""
Yojana Saathi - Controlled Action Dispatcher
============================================
Dispatches validated AgentActions to strictly allowlisted handlers.
Directly invokes the Phase 1 Deterministic Eligibility Engine as an authoritative tool.
"""

from typing import Any, Callable, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.agent.actions import ActionType, AgentAction
from backend.app.agent.state import AgentState, StageEnum, TerminationReason
from backend.app.agent.validator import ActionValidator
from backend.app.schemas.eligibility import SchemeOutcome
from backend.app.schemas.profile import CitizenProfile
from backend.app.services.eligibility_engine import evaluate_all_schemes
from backend.app.services.scheme_loader import load_all_schemes


class ActionDispatcher:
    """
    Controlled dispatcher executing only allowlisted handlers.
    Arbitrary execution is strictly impossible.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._handlers: Dict[ActionType, Callable[[AgentAction, AgentState], Dict[str, Any]]] = {
            ActionType.ASK_QUESTION: self._handle_ask_question,
            ActionType.RUN_ELIGIBILITY: self._handle_run_eligibility,
            ActionType.EVALUATE_SCHEMES: self._handle_evaluate_schemes,
            ActionType.SELECT_SCHEMES: self._handle_select_schemes,
            ActionType.CREATE_APPLICATIONS: self._handle_select_schemes,
            ActionType.SWITCH_ACTIVE_APPLICATION: self._handle_switch_active_application,
            ActionType.REEVALUATE_SCHEMES: self._handle_reevaluate_schemes,
            ActionType.REQUEST_DOCUMENT: self._handle_request_document,
            ActionType.PROCESS_DOCUMENT: self._handle_process_document,
            ActionType.VERIFY_DOCUMENT: self._handle_verify_document,
            ActionType.RESOLVE_DOCUMENT_DISCREPANCY: self._handle_resolve_document_discrepancy,
            ActionType.CALCULATE_READINESS: self._handle_calculate_readiness,
            ActionType.READY_FOR_HANDOFF: self._handle_ready_for_handoff,
            ActionType.RESOLVE_CONTRADICTION: self._handle_resolve_contradiction,
            ActionType.NO_SUPPORTED_MATCH: self._handle_no_supported_match,
            ActionType.ESCALATE_HUMAN: self._handle_escalate_human,
            ActionType.FINISH: self._handle_finish,
            ActionType.REQUEST_CLARIFICATION: self._handle_request_clarification,
            ActionType.REEVALUATE_CANDIDATES: self._handle_reevaluate_candidates,
        }

    def dispatch(self, action: AgentAction, state: AgentState) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Validates and executes an action.
        
        Returns:
            (success, execution_result_dict, error_message)
        """
        is_valid, error_msg = ActionValidator.validate(action, state)
        if not is_valid:
            return False, {}, error_msg

        handler = self._handlers.get(action.action)
        if not handler:
            return False, {}, f"No execution handler registered for action: {action.action.value}"

        result = handler(action, state)
        return True, result, None

    def _handle_ask_question(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        target_field = action.field or "general"
        question_text = action.question or "Please provide additional information."

        state.add_asked_question(target_field, question_text)
        state.stage = StageEnum.WAITING_FOR_USER_INPUT.value

        return {
            "action_executed": ActionType.ASK_QUESTION.value,
            "field": target_field,
            "question": question_text,
            "status": "WAITING_USER_INPUT",
        }

    def _handle_run_eligibility(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        """
        Executes Phase 1 Deterministic Eligibility Engine as an authoritative tool.
        """
        profile_obj = CitizenProfile.model_validate(state.profile)

        # Load schemes to evaluate (filter to candidates if specified)
        all_schemes = load_all_schemes()
        if len(state.candidate_schemes) > 0:
            schemes_to_eval = [s for s in all_schemes if s.scheme_id in state.candidate_schemes]
        else:
            schemes_to_eval = all_schemes

        # Deterministic evaluation using Phase 1 service
        multi_result = evaluate_all_schemes(profile_obj, schemes_to_eval)

        # Update persistent state with authoritative results
        state.evaluated_schemes = list(multi_result.evaluations.keys())
        state.eligible_schemes = list(multi_result.fully_eligible_schemes) + list(multi_result.actionable_schemes)
        state.eliminated_schemes = list(multi_result.not_eligible_schemes)
        state.scheme_evaluations = {
            s_id: {
                "outcome": ev.outcome.value if hasattr(ev.outcome, "value") else str(ev.outcome),
                "profile_fingerprint": state.get_profile_fingerprint(),
                "selectable": ev.outcome in [
                    SchemeOutcome.FULLY_ELIGIBLE,
                    SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED,
                    "FULLY_ELIGIBLE",
                    "ACTIONABLE_PREPARATION_REQUIRED",
                ],
                "summary": ev.summary_reason,
            }
            for s_id, ev in multi_result.evaluations.items()
        }
        state.scheme_missing_information = {
            s_id: sorted(list(set(ev.missing_critical_fields + [c.field for c in ev.unresolved_criteria])))
            for s_id, ev in multi_result.evaluations.items()
        }
        state.evaluated_profile_fingerprint = state.get_profile_fingerprint()
        state.stage = StageEnum.ELIGIBILITY_EVALUATED.value

        return {
            "action_executed": ActionType.RUN_ELIGIBILITY.value,
            "total_evaluated": multi_result.total_schemes_evaluated,
            "fully_eligible": multi_result.fully_eligible_schemes,
            "actionable": multi_result.actionable_schemes,
            "not_eligible": multi_result.not_eligible_schemes,
            "incomplete": multi_result.incomplete_schemes,
        }

    def _handle_resolve_contradiction(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        state.stage = StageEnum.CONTRADICTION_RESOLUTION.value
        return {
            "action_executed": ActionType.RESOLVE_CONTRADICTION.value,
            "field": action.field,
            "prompt": action.question,
            "status": "WAITING_CONTRADICTION_RESOLUTION",
        }

    def _handle_no_supported_match(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        state.mark_terminated(TerminationReason.NO_SUPPORTED_MATCH)
        return {
            "action_executed": ActionType.NO_SUPPORTED_MATCH.value,
            "message": "No configured government schemes match the confirmed citizen profile.",
            "status": "TERMINAL",
        }

    def _handle_escalate_human(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        state.mark_terminated(TerminationReason.HUMAN_VERIFICATION_REQUIRED)
        state.stage = StageEnum.ESCALATED.value
        return {
            "action_executed": ActionType.ESCALATE_HUMAN.value,
            "message": "Case escalated to CSC operator or official channel for human verification.",
            "status": "ESCALATED",
        }

    def _handle_finish(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        state.mark_terminated(TerminationReason.OBJECTIVE_COMPLETE)
        return {
            "action_executed": ActionType.FINISH.value,
            "eligible_schemes": state.eligible_schemes,
            "status": "COMPLETE",
        }

    def _handle_request_clarification(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        state.stage = StageEnum.WAITING_FOR_USER_INPUT.value
        return {
            "action_executed": ActionType.REQUEST_CLARIFICATION.value,
            "question": action.question,
            "status": "WAITING_USER_INPUT",
        }

    def _handle_reevaluate_candidates(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        # Filter candidate schemes based on known profile
        all_schemes = load_all_schemes()
        candidates = []
        user_state = state.profile.get("state")
        user_occ = state.profile.get("occupation")

        for s in all_schemes:
            if s.state_restriction and user_state and s.state_restriction.lower() != str(user_state).lower():
                continue
            candidates.append(s.scheme_id)

        state.candidate_schemes = candidates
        return {
            "action_executed": ActionType.REEVALUATE_CANDIDATES.value,
            "candidate_count": len(candidates),
        }

    def _handle_evaluate_schemes(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
        items = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)
        return {
            "action_executed": ActionType.EVALUATE_SCHEMES.value,
            "total_evaluated": len(items),
            "fully_eligible": [i.scheme_id for i in items if i.outcome == "FULLY_ELIGIBLE"],
            "actionable": [i.scheme_id for i in items if i.outcome == "ACTIONABLE_PREPARATION_REQUIRED"],
            "not_eligible": [i.scheme_id for i in items if i.outcome == "NOT_ELIGIBLE"],
            "incomplete": [i.scheme_id for i in items if i.outcome == "INCOMPLETE / UNKNOWN"],
        }

    def _handle_select_schemes(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        selected_ids = action.arguments.get("selected_scheme_ids", [])
        for s_id in selected_ids:
            if s_id not in state.selected_schemes:
                state.selected_schemes.append(s_id)
            if s_id not in state.applications:
                state.applications[s_id] = {"id": f"APP-{s_id}", "status": "SELECTED"}
        if not state.active_scheme_id and selected_ids:
            state.active_scheme_id = selected_ids[0]
            state.active_application_id = state.applications[selected_ids[0]].get("id")
        return {
            "action_executed": ActionType.SELECT_SCHEMES.value,
            "selected_schemes": selected_ids,
            "active_scheme_id": state.active_scheme_id,
        }

    def _handle_switch_active_application(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
        target = action.field or action.arguments.get("scheme_id") or action.arguments.get("application_id")
        scheme_id, app_id = MultiSchemeCoordinator.switch_active_application(state, target)
        return {
            "action_executed": ActionType.SWITCH_ACTIVE_APPLICATION.value,
            "active_scheme_id": scheme_id,
            "active_application_id": app_id,
        }

    def _handle_reevaluate_schemes(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.multi_scheme_coordinator import MultiSchemeCoordinator
        items = MultiSchemeCoordinator.evaluate_all_candidate_schemes(state)
        return {
            "action_executed": ActionType.REEVALUATE_SCHEMES.value,
            "total_evaluated": len(items),
        }

    def _handle_request_document(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        doc_type = action.field or action.arguments.get("document_type")
        app_id = action.arguments.get("application_id") or state.active_application_id
        if not hasattr(state, "requested_documents"):
            state.requested_documents = []
        state.requested_documents.append({"document_type": doc_type, "application_id": app_id})
        return {
            "action_executed": ActionType.REQUEST_DOCUMENT.value,
            "requested_document": doc_type,
            "application_id": app_id,
        }

    def _handle_process_document(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.document_coordinator import DocumentCoordinator
        doc_id = action.field or action.arguments.get("document_id")
        app_id = action.arguments.get("application_id") or state.active_application_id
        coord = DocumentCoordinator()
        res = coord.process_and_verify_document(state, doc_id, app_id, db=self.db)
        return {
            "action_executed": ActionType.PROCESS_DOCUMENT.value,
            "document_id": doc_id,
            "extraction_status": res.extraction_status,
            "verification_status": res.verification_status,
            "discrepancies_count": len(res.discrepancies),
        }

    def _handle_verify_document(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        return self._handle_process_document(action, state)

    def _handle_resolve_document_discrepancy(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.document_coordinator import DocumentCoordinator
        disc_id = action.field or action.arguments.get("discrepancy_id")
        resolution = action.arguments.get("resolution", "KEEP_PROFILE")
        coord = DocumentCoordinator()
        res = coord.resolve_discrepancy(state, disc_id, resolution, db=self.db)
        return {
            "action_executed": ActionType.RESOLVE_DOCUMENT_DISCREPANCY.value,
            "discrepancy_id": disc_id,
            "resolution": resolution,
            "status": res["status"],
        }

    def _handle_calculate_readiness(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        from backend.app.services.document_coordinator import DocumentCoordinator
        app_id = action.field or action.arguments.get("application_id") or state.active_application_id
        coord = DocumentCoordinator()
        readiness = coord.compute_readiness(state, app_id, db=self.db)
        return {
            "action_executed": ActionType.CALCULATE_READINESS.value,
            "application_id": app_id,
            "readiness_status": readiness.status,
            "total_requirements": readiness.total_requirements,
            "verified_requirements": readiness.verified_requirements,
        }

    def _handle_ready_for_handoff(self, action: AgentAction, state: AgentState) -> Dict[str, Any]:
        app_id = action.field or action.arguments.get("application_id") or state.active_application_id
        # Update application status
        for s_id, app_info in state.applications.items():
            if app_info.get("id") == app_id or s_id == app_id:
                app_info["status"] = "READY_FOR_HANDOFF"
                break
        state.stage = "READY_FOR_HANDOFF"
        return {
            "action_executed": ActionType.READY_FOR_HANDOFF.value,
            "application_id": app_id,
            "status": "READY_FOR_HANDOFF",
        }

