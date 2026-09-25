"""
Yojana Saathi - Profile Persistence Service
===========================================
Atomic transactional persistence for profile confirmations, rejections, and staleness invalidation.
Ensures that confirmed profile updates, fingerprinting, and staleness marks succeed or fail as a single unit.
"""

from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.agent.state import AgentState
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.evaluation_repository import SchemeEvaluationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.repositories.profile_repository import ProfileRepository
from backend.app.profile.confirmation import ConfirmationManager
from backend.app.profile.schemas import ProfileConfirmation


def confirm_and_persist_profile(
    db: Session,
    state: AgentState,
    expected_version: Optional[int] = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    Transactionally applies and persists a pending profile confirmation.
    1. Validates and applies patch to in-memory AgentState.
    2. Upserts confirmed profile with fingerprint and incremented version.
    3. If confirmed fields invalidate previous evaluations, marks them stale in DB.
    4. Marks HumanConfirmation record as CONFIRMED.
    5. Records agent observability event.
    """
    if not state.pending_confirmation:
        raise ValueError("No pending profile confirmation exists in state.")

    confirmation_id = state.pending_confirmation.get("confirmation_id")
    confirmation = ProfileConfirmation.model_validate(state.pending_confirmation)

    # Apply in-memory confirmation & calculate staleness
    updated_profile, eligibility_invalidated = ConfirmationManager.apply_confirmation(
        confirmation, state
    )
    state.recompute_missing_information()

    # Begin DB transaction
    try:
        # 1. Update Profile record with optimistic concurrency check
        ProfileRepository.upsert_profile(
            db=db,
            case_id=state.case_id,
            profile_data=state.profile,
            fingerprint=state.get_profile_fingerprint(),
            confirmed=True,
            expected_version=expected_version,
        )

        # 2. Invalidate stale evaluations if profile changed
        if eligibility_invalidated:
            SchemeEvaluationRepository.mark_evaluations_stale(db, state.case_id)

        # 3. Resolve confirmation record
        if confirmation_id:
            ConfirmationRepository.resolve_confirmation(db, confirmation_id, "CONFIRMED")

        # 4. Update parent case stage & missing information
        CaseRepository.update_case(
            db=db,
            case_id=state.case_id,
            stage=state.stage,
            missing_information=state.missing_information,
        )

        # 5. Record observability event
        EventRepository.record_agent_event(
            db=db,
            case_id=state.case_id,
            iteration=state.iteration,
            stage=state.stage,
            action="CONFIRM_PROFILE",
            reason_code="HUMAN_CONFIRMED",
            state_fingerprint=state.get_fingerprint(),
            event_data={
                "confirmed_fields": list(confirmation.raw_patch.keys()),
                "eligibility_invalidated": eligibility_invalidated,
            },
        )

        db.commit()
        return updated_profile, eligibility_invalidated

    except Exception:
        db.rollback()
        raise


def reject_and_persist_profile(
    db: Session,
    state: AgentState,
) -> Dict[str, Any]:
    """
    Transactionally rejects a pending profile patch.
    Confirmed profile in PostgreSQL remains completely untouched.
    """
    if not state.pending_confirmation:
        raise ValueError("No pending profile confirmation exists in state.")

    confirmation_id = state.pending_confirmation.get("confirmation_id")
    confirmation = ProfileConfirmation.model_validate(state.pending_confirmation)

    ConfirmationManager.reject_confirmation(confirmation, state)

    try:
        if confirmation_id:
            ConfirmationRepository.resolve_confirmation(db, confirmation_id, "REJECTED")

        CaseRepository.update_case(
            db=db,
            case_id=state.case_id,
            stage=state.stage,
        )

        EventRepository.record_agent_event(
            db=db,
            case_id=state.case_id,
            iteration=state.iteration,
            stage=state.stage,
            action="REJECT_PROFILE",
            reason_code="HUMAN_REJECTED",
            state_fingerprint=state.get_fingerprint(),
            event_data={"rejected_fields": list(confirmation.raw_patch.keys())},
        )

        db.commit()
        return state.profile

    except Exception:
        db.rollback()
        raise
