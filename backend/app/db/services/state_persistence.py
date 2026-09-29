"""
Yojana Saathi - State Persistence Service
=========================================
Hydrates and persists AgentState to/from PostgreSQL without coupling AgentController to SQL.
Maps core domain entities relationally (cases, profiles, applications, evaluations, events).
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.agent.actions import AgentAction, AgentActivity
from backend.app.agent.state import AgentState, Contradiction, StageEnum
from backend.app.db.models.case import Case
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.profile_repository import ProfileRepository


def load_case(db: Session, case_id: str) -> Optional[AgentState]:
    """
    Loads a case and reconstructs its full in-memory AgentState.
    Avoids N+1 query patterns by loading relations cleanly.
    """
    case = CaseRepository.get_case_with_relations(db, case_id)
    if not case:
        return None

    # 1. Profile facts
    profile_dict: Dict[str, Any] = {}
    evaluated_fp: Optional[str] = None
    if case.profile:
        profile_dict = dict(case.profile.profile_data)

    # 2. Scheme Applications
    applications_dict = {
        app.scheme_id: {"id": app.id, "status": app.status}
        for app in case.applications
    }
    selected_schemes = [app.scheme_id for app in case.applications]
    active_scheme_id = selected_schemes[0] if selected_schemes else None
    active_application_id = applications_dict[active_scheme_id]["id"] if active_scheme_id else None

    # 3. Active Evaluations
    eligible: List[str] = []
    eliminated: List[str] = []
    evaluated: List[str] = []
    scheme_evals_dict: Dict[str, Dict[str, Any]] = {}
    for ev in case.evaluations:
        if not ev.is_stale:
            evaluated_fp = ev.profile_fingerprint
            evaluated.append(ev.scheme_id)
            scheme_evals_dict[ev.scheme_id] = {
                "outcome": ev.outcome,
                "reasons": ev.reasons,
                "profile_fingerprint": ev.profile_fingerprint,
                "rules_version": ev.rules_version,
            }
            if ev.outcome in ["FULLY_ELIGIBLE", "ACTIONABLE_PREPARATION_REQUIRED"]:
                eligible.append(ev.scheme_id)
            elif ev.outcome == "NOT_ELIGIBLE":
                eliminated.append(ev.scheme_id)

    # 4. Pending Confirmation
    pending_conf_dict: Optional[Dict[str, Any]] = None
    pending_conf = ConfirmationRepository.get_pending_by_case_id(db, case_id)
    if pending_conf:
        pending_conf_dict = {
            "confirmation_id": pending_conf.id,
            "status": pending_conf.status,
            "confirmation_required": True,
            "changes": pending_conf.proposed_changes,
            "raw_patch": pending_conf.raw_patch or {},
        }

    # 5. Conversation & Event History
    history: List[Dict[str, Any]] = []
    asked: List[str] = []
    for ev in sorted(case.agent_events, key=lambda x: x.iteration):
        history.append({
            "speaker": "agent",
            "action": ev.action,
            "field": ev.selected_field,
            "iteration": ev.iteration,
            "event_data": ev.event_data,
        })
        if ev.action == "ASK_QUESTION" and ev.selected_field and ev.selected_field not in asked:
            asked.append(ev.selected_field)

    # Reconstruct AgentState
    state = AgentState(
        case_id=case.id,
        goal=case.goal,
        profile=profile_dict,
        candidate_schemes=list(case.candidate_schemes),
        evaluated_schemes=evaluated,
        scheme_evaluations=scheme_evals_dict,
        missing_information=list(case.missing_information),
        eligible_schemes=eligible,
        eliminated_schemes=eliminated,
        selected_schemes=selected_schemes,
        applications=applications_dict,
        active_scheme_id=active_scheme_id,
        active_application_id=active_application_id,
        pending_confirmation=pending_conf_dict,
        evaluated_profile_fingerprint=evaluated_fp,
        asked_questions=asked,
        conversation_history=history,
        language_preference=case.metadata_json.get("language_preference", "en") if case.metadata_json else "en",
        documents=case.metadata_json.get("documents", []) if (case.metadata_json and "documents" in case.metadata_json) else ([{"id": d.id, "document_type": d.document_type, "status": d.status} for d in case.documents] if hasattr(case, "documents") and case.documents else []),
        stage=case.stage,
        iteration=case.iteration,
        max_iterations=case.max_iterations,
    )

    return state


def persist_agent_state(
    db: Session,
    state: AgentState,
    activity: Optional[AgentActivity] = None,
    expected_profile_version: Optional[int] = None,
) -> Case:
    """
    Transactionally persists the current AgentState to PostgreSQL.
    """
    # 1. Update or create Case
    case = CaseRepository.get_case(db, state.case_id)
    if not case:
        case = CaseRepository.create_case(
            db=db,
            case_id=state.case_id,
            goal=state.goal,
            candidate_schemes=state.candidate_schemes,
        )

    case.stage = state.stage
    case.iteration = state.iteration
    case.max_iterations = state.max_iterations
    case.candidate_schemes = state.candidate_schemes
    case.missing_information = state.missing_information

    # Persist language preference and documents in case metadata
    meta = dict(case.metadata_json or {})
    meta["language_preference"] = getattr(state, "language_preference", "en")
    meta["documents"] = list(getattr(state, "documents", []))
    case.metadata_json = meta

    # 2. Persist Confirmed Profile
    if state.profile:
        ProfileRepository.upsert_profile(
            db=db,
            case_id=state.case_id,
            profile_data=state.profile,
            fingerprint=state.get_profile_fingerprint(),
            confirmed=True,
            expected_version=expected_profile_version,
        )

    # 3. Persist Applications (only for explicitly selected schemes or active applications)
    schemes_to_persist = state.selected_schemes or list(state.applications.keys())
    for scheme_id in schemes_to_persist:
        existing_app = ApplicationRepository.get_by_case_and_scheme(db, state.case_id, scheme_id)
        app_status = state.applications.get(scheme_id, {}).get("status", "SELECTED")
        if not existing_app:
            new_app = ApplicationRepository.create_application(db, state.case_id, scheme_id, app_status)
            state.applications[scheme_id] = {"id": new_app.id, "status": new_app.status}
        elif existing_app.status != app_status:
            ApplicationRepository.update_status(db, existing_app.id, app_status)

    # 4. Persist Agent Activity Event if supplied
    if activity:
        EventRepository.record_agent_event(
            db=db,
            case_id=state.case_id,
            iteration=activity.iteration,
            stage=activity.stage,
            action=activity.selected_action,
            reason_code=activity.reason_code,
            selected_field=activity.selected_field,
            state_fingerprint=activity.state_fingerprint,
            event_data={
                "tool_called": activity.tool_called,
                "missing_information": activity.missing_information,
                "candidate_count": activity.candidate_schemes_count,
                "termination_reason": activity.termination_reason,
            },
        )

    db.commit()
    db.refresh(case)
    return case
