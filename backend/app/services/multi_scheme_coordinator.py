"""
Yojana Saathi - Multi-Scheme Coordinator
=========================================
Central coordinator for Phase 4 multi-scheme evaluation, selection,
application track orchestration, and lifecycle tracking.
Strictly deterministic with ZERO ranking, scoring, or LLM-based decisions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.agent.actions import ReasonCode
from backend.app.agent.state import AgentState, StageEnum, TerminationReason
from backend.app.db.models.application import Application
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.scheme_repository import SchemeRepository
from backend.app.schemas.eligibility import (
    CriterionStatus,
    MultiSchemeEvaluationResult,
    SchemeEvaluationResult,
    SchemeOutcome,
)
from backend.app.schemas.multi_scheme import (
    ApplicationItemResponse,
    ApplicationStatus,
    SchemeOutcomeItem,
)
from backend.app.schemas.profile import CitizenProfile
from backend.app.services.eligibility_engine import evaluate_all_schemes
from backend.app.services.scheme_loader import load_all_schemes, get_scheme

logger = logging.getLogger(__name__)


class MultiSchemeCoordinator:
    """
    Deterministic coordinator managing independent evaluation and application tracks
    across multiple government schemes without evaluative ranking.
    """

    @classmethod
    def evaluate_all_candidate_schemes(
        cls,
        state: AgentState,
        db: Optional[Session] = None,
        schemes_to_evaluate: Optional[List[Any]] = None,
    ) -> List[SchemeOutcomeItem]:
        """
        Evaluates all candidate or configured schemes independently using the Phase 1 engine.
        Results are tied to the current confirmed profile fingerprint.
        """
        # Gating check: profile changes pending confirmation must be resolved first
        if state.pending_confirmation:
            raise ValueError("Cannot evaluate schemes while profile changes are pending human confirmation.")

        # Contradiction check
        active_contradictions = [c for c in state.contradictions if not c.resolved]
        if active_contradictions:
            raise ValueError(f"Cannot evaluate schemes while {len(active_contradictions)} unresolved contradiction(s) exist.")

        profile_obj = CitizenProfile.model_validate(state.profile)
        current_fingerprint = state.get_profile_fingerprint()

        # Load schemes to evaluate (filter to candidates if specified, otherwise load all configured)
        all_catalog_schemes = load_all_schemes()
        if schemes_to_evaluate:
            schemes = schemes_to_evaluate
        elif state.candidate_schemes and len(state.candidate_schemes) > 0:
            schemes = [s for s in all_catalog_schemes if s.scheme_id in state.candidate_schemes]
        else:
            schemes = all_catalog_schemes

        # Phase 1 Deterministic Evaluation
        multi_result: MultiSchemeEvaluationResult = evaluate_all_schemes(profile_obj, schemes)

        outcome_items: List[SchemeOutcomeItem] = []
        scheme_missing_map: Dict[str, List[str]] = {}
        fully_eligible: List[str] = []
        actionable: List[str] = []
        not_eligible: List[str] = []
        incomplete: List[str] = []
        evaluated_scheme_ids: List[str] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        # If DB session provided, mark any old active evaluations stale before persisting new ones
        if db:
            SchemeEvaluationRepository.mark_evaluations_stale(db, state.case_id)

        for scheme_def in schemes:
            s_id = scheme_def.scheme_id
            evaluated_scheme_ids.append(s_id)
            eval_res = multi_result.evaluations.get(s_id)
            if not eval_res:
                continue

            outcome_str = eval_res.outcome.value if hasattr(eval_res.outcome, "value") else str(eval_res.outcome)
            is_fully_eligible = eval_res.outcome == SchemeOutcome.FULLY_ELIGIBLE
            is_actionable = eval_res.outcome == SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED
            is_selectable = is_fully_eligible or is_actionable

            if is_fully_eligible:
                fully_eligible.append(s_id)
            elif is_actionable:
                actionable.append(s_id)
            elif eval_res.outcome == SchemeOutcome.NOT_ELIGIBLE:
                not_eligible.append(s_id)
            else:
                incomplete.append(s_id)

            # Scheme-specific missing information
            missing_for_scheme = sorted(list(set(
                eval_res.missing_critical_fields + [c.field for c in eval_res.unresolved_criteria]
            )))
            scheme_missing_map[s_id] = missing_for_scheme

            # Check if an application already exists for this scheme
            existing_app_id = None
            if s_id in state.applications:
                existing_app_id = state.applications[s_id].get("id")
            elif db:
                db_app = ApplicationRepository.get_by_case_and_scheme(db, state.case_id, s_id)
                if db_app:
                    existing_app_id = db_app.id

            item = SchemeOutcomeItem(
                scheme_id=s_id,
                scheme_name=scheme_def.title_en,
                outcome=outcome_str,
                eligible=is_selectable,
                selectable=is_selectable,
                missing_information=missing_for_scheme,
                failed_conditions=[
                    {"field": c.field, "reason": c.reason, "operator": c.operator, "actual": c.actual}
                    for c in eval_res.failed_criteria
                ],
                unknown_conditions=[
                    {"field": c.field, "reason": c.reason, "operator": c.operator}
                    for c in eval_res.unresolved_criteria
                ],
                reasons=[eval_res.summary_reason] if eval_res.summary_reason else [],
                summary_reason=eval_res.summary_reason,
                profile_fingerprint=current_fingerprint,
                rules_version=scheme_def.schema_version or "2.0",
                evaluated_at=now_iso,
                application_id=existing_app_id,
            )
            outcome_items.append(item)

            # Persist to PostgreSQL if DB session provided
            if db:
                SchemeEvaluationRepository.record_evaluation(
                    db=db,
                    case_id=state.case_id,
                    scheme_id=s_id,
                    profile_fingerprint=current_fingerprint,
                    outcome=outcome_str,
                    reasons={
                        "summary": eval_res.summary_reason,
                        "failed_criteria": [c.model_dump() for c in eval_res.failed_criteria],
                        "unresolved_criteria": [c.model_dump() for c in eval_res.unresolved_criteria],
                        "missing_critical": eval_res.missing_critical_fields,
                    },
                    rules_version=scheme_def.schema_version or "2.0",
                    application_id=existing_app_id,
                )

        # Update AgentState
        state.evaluated_schemes = evaluated_scheme_ids
        state.eligible_schemes = fully_eligible + actionable
        state.eliminated_schemes = not_eligible
        state.scheme_evaluations = {
            item.scheme_id: item.model_dump() for item in outcome_items
        }
        state.scheme_missing_information = scheme_missing_map
        state.evaluated_profile_fingerprint = current_fingerprint

        # Determine next stage
        if len(state.eligible_schemes) > 0:
            state.stage = StageEnum.ELIGIBILITY_EVALUATED.value
        elif len(incomplete) > 0 and len(fully_eligible) == 0 and len(actionable) == 0:
            state.stage = StageEnum.MISSING_INFO_COLLECTION.value
        elif len(not_eligible) == len(schemes):
            state.stage = StageEnum.ELIGIBILITY_EVALUATED.value

        # Record Agent Event if db provided
        if db:
            EventRepository.record_agent_event(
                db=db,
                case_id=state.case_id,
                iteration=state.iteration,
                stage=state.stage,
                action="EVALUATE_SCHEMES",
                reason_code=ReasonCode.SCHEMES_EVALUATED.value,
                state_fingerprint=state.get_fingerprint(),
                event_data={
                    "total_evaluated": len(schemes),
                    "fully_eligible": fully_eligible,
                    "actionable": actionable,
                    "not_eligible": not_eligible,
                    "incomplete": incomplete,
                    "profile_fingerprint": current_fingerprint,
                },
            )
            db.commit()

        return outcome_items

    @classmethod
    def select_schemes(
        cls,
        state: AgentState,
        selected_scheme_ids: List[str],
        db: Optional[Session] = None,
    ) -> List[Any]:
        """
        Transactional selection of one or more eligible/actionable schemes.
        Creates one Application track per selected scheme with UNIQUE(case_id, scheme_id).
        Rejects invalid, duplicate, stale, or not-eligible selections atomically.
        """
        if not selected_scheme_ids:
            raise ValueError("Selection request must contain at least one scheme ID.")

        # Check duplicate scheme IDs in request
        if len(selected_scheme_ids) != len(set(selected_scheme_ids)):
            raise ValueError("Duplicate scheme IDs detected in selection request.")

        current_fp = state.get_profile_fingerprint()

        # Validation gate for every requested scheme
        all_catalog = {s.scheme_id: s for s in load_all_schemes()}
        for s_id in selected_scheme_ids:
            # 1. Catalog existence
            if s_id not in all_catalog:
                raise ValueError(f"Scheme '{s_id}' does not exist in the configured catalog.")

            # 2. Evaluation existence & freshness
            eval_data = state.scheme_evaluations.get(s_id)
            if not eval_data:
                # Check DB for current evaluation if db is available
                if db:
                    db_evals = SchemeEvaluationRepository.list_active_for_case(db, state.case_id)
                    db_match = next((e for e in db_evals if e.scheme_id == s_id and not e.is_stale), None)
                    if not db_match:
                        raise ValueError(f"Scheme '{s_id}' has not been evaluated for case '{state.case_id}'.")
                    eval_data = {
                        "outcome": db_match.outcome,
                        "profile_fingerprint": db_match.profile_fingerprint,
                        "selectable": db_match.outcome in ["FULLY_ELIGIBLE", "ACTIONABLE_PREPARATION_REQUIRED"],
                    }
                else:
                    raise ValueError(f"Scheme '{s_id}' has not been evaluated for case '{state.case_id}'.")

            # 3. Fingerprint freshness
            eval_fp = eval_data.get("profile_fingerprint")
            if eval_fp != current_fp:
                raise ValueError(
                    f"Scheme '{s_id}' evaluation is stale (evaluated on profile {eval_fp}, current is {current_fp}). "
                    f"Reevaluation is required before selection."
                )

            # 4. Selectable outcome check (FULLY_ELIGIBLE or ACTIONABLE_PREPARATION_REQUIRED)
            outcome = eval_data.get("outcome")
            is_selectable = outcome in [
                SchemeOutcome.FULLY_ELIGIBLE.value,
                SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED.value,
                "FULLY_ELIGIBLE",
                "ACTIONABLE_PREPARATION_REQUIRED",
            ]
            if not is_selectable:
                raise ValueError(
                    f"Scheme '{s_id}' cannot be selected because its outcome is '{outcome}'. "
                    f"Only FULLY_ELIGIBLE or ACTIONABLE_PREPARATION_REQUIRED schemes are selectable."
                )

        # Atomic transaction to create application tracks
        created_or_retrieved_apps: List[Any] = []
        try:
            for s_id in selected_scheme_ids:
                eval_data = state.scheme_evaluations.get(s_id, {})
                outcome = eval_data.get("outcome", "FULLY_ELIGIBLE")
                initial_status = (
                    ApplicationStatus.ACTIONABLE.value
                    if outcome in [SchemeOutcome.ACTIONABLE_PREPARATION_REQUIRED.value, "ACTIONABLE_PREPARATION_REQUIRED"]
                    else ApplicationStatus.SELECTED.value
                )

                if db:
                    existing_app = ApplicationRepository.get_by_case_and_scheme(db, state.case_id, s_id)
                    if existing_app:
                        app_record = existing_app
                    else:
                        app_record = ApplicationRepository.create_application(
                            db=db,
                            case_id=state.case_id,
                            scheme_id=s_id,
                            status=initial_status,
                        )
                        # Record application created event
                        EventRepository.record_application_event(
                            db=db,
                            application_id=app_record.id,
                            event_type="APPLICATION_CREATED",
                            event_data={
                                "scheme_id": s_id,
                                "initial_status": initial_status,
                                "profile_fingerprint": current_fp,
                            },
                        )

                    # Record scheme selected event
                    EventRepository.record_application_event(
                        db=db,
                        application_id=app_record.id,
                        event_type="SCHEME_SELECTED",
                        event_data={
                            "scheme_id": s_id,
                            "outcome": outcome,
                            "profile_fingerprint": current_fp,
                        },
                    )
                else:
                    # In-memory mock record
                    import uuid
                    existing_id = state.applications.get(s_id, {}).get("id")
                    app_id = existing_id or f"app_{uuid.uuid4().hex[:12]}"
                    from types import SimpleNamespace
                    app_record = SimpleNamespace(id=app_id, scheme_id=s_id, status=initial_status)

                created_or_retrieved_apps.append(app_record)

                # Update in-memory state
                if s_id not in state.selected_schemes:
                    state.selected_schemes.append(s_id)
                state.applications[s_id] = {
                    "id": app_record.id,
                    "status": app_record.status,
                }

            # Set active scheme if not already set
            if not state.active_scheme_id and selected_scheme_ids:
                state.active_scheme_id = selected_scheme_ids[0]
                state.active_application_id = created_or_retrieved_apps[0].id

            # Persist structured agent event if db is available
            if db:
                EventRepository.record_agent_event(
                    db=db,
                    case_id=state.case_id,
                    iteration=state.iteration,
                    stage=state.stage,
                    action="SELECT_SCHEMES",
                    reason_code=ReasonCode.SCHEMES_SELECTED.value,
                    state_fingerprint=state.get_fingerprint(),
                    event_data={
                        "selected_scheme_ids": selected_scheme_ids,
                        "application_ids": [a.id for a in created_or_retrieved_apps],
                    },
                )
                db.commit()
                for a in created_or_retrieved_apps:
                    db.refresh(a)

            return created_or_retrieved_apps

        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Multi-scheme selection transaction failed: {e}")
            raise

    @classmethod
    def update_application_status(
        cls,
        state: AgentState,
        application_id: str,
        new_status: str,
        db: Optional[Session] = None,
    ) -> Any:
        """
        Updates the status of a specific application track.
        Guarantees that other applications for the same case remain completely unchanged.
        """
        if db:
            app = ApplicationRepository.get_application(db, application_id)
            if not app:
                raise ValueError(f"Application '{application_id}' not found.")

            old_status = app.status
            updated_app = ApplicationRepository.update_status(db, application_id, new_status)

            # Record event
            EventRepository.record_application_event(
                db=db,
                application_id=application_id,
                event_type="APPLICATION_STATUS_CHANGED",
                event_data={"old_status": old_status, "new_status": new_status},
            )

            db.commit()
            db.refresh(updated_app)

            # Sync in-memory state
            if app.scheme_id in state.applications:
                state.applications[app.scheme_id]["status"] = new_status

            return updated_app
        else:
            # In-memory update
            found_scheme = None
            for s_id, app_info in state.applications.items():
                if app_info.get("id") == application_id:
                    found_scheme = s_id
                    app_info["status"] = new_status
                    break
            if not found_scheme:
                raise ValueError(f"Application '{application_id}' not found in state.")
            from types import SimpleNamespace
            return SimpleNamespace(id=application_id, scheme_id=found_scheme, status=new_status)

    @classmethod
    def switch_active_application(
        cls,
        state: AgentState,
        scheme_id_or_app_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Switches the conversational active application track without modifying other tracks.
        """
        target_scheme_id = None
        target_app_id = None

        if scheme_id_or_app_id in state.applications:
            target_scheme_id = scheme_id_or_app_id
            target_app_id = state.applications[scheme_id_or_app_id].get("id")
        else:
            for s_id, app_info in state.applications.items():
                if app_info.get("id") == scheme_id_or_app_id:
                    target_scheme_id = s_id
                    target_app_id = scheme_id_or_app_id
                    break

        if not target_scheme_id:
            raise ValueError(f"Cannot switch to '{scheme_id_or_app_id}': not in case applications.")

        state.active_scheme_id = target_scheme_id
        state.active_application_id = target_app_id
        return target_scheme_id, target_app_id
