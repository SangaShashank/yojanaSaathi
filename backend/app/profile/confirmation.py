"""
Yojana Saathi - Human / CSC Confirmation Manager
================================================
Guarantees the core safety boundary:
- Gemini only PROPOSES facts.
- Facts NEVER become authoritative without explicit Human/CSC Confirmation.
- Phase 1 Deterministic Eligibility Engine only receives confirmed facts.
- Invalidation / Staleness: when confirmed profile updates, stale eligibility evaluations are invalidated.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from backend.app.agent.state import AgentState, Contradiction, StageEnum
from backend.app.profile.patcher import ProfilePatcher
from backend.app.profile.schemas import (
    ConfirmationStatus,
    ProfileActivityEvent,
    ProfileChangeItem,
    ProfileConfirmation,
    ProfilePatch,
)
from backend.app.schemas.profile import CitizenProfile

logger = logging.getLogger(__name__)


class ConfirmationManager:
    """
    Manages the lifecycle of proposed profile patches:
    PROPOSED -> PENDING -> CONFIRMED / REJECTED / CORRECTED
    """

    @staticmethod
    def create_pending_confirmation(
        current_profile: Dict[str, Any], patch: ProfilePatch
    ) -> ProfileConfirmation:
        """
        Creates a pending confirmation object with human/CSC-friendly diff items.
        """
        change_items = ProfilePatcher.generate_change_items(current_profile, patch)
        
        # Check for contradictions
        contradictions = ProfilePatcher.detect_contradictions(current_profile, patch)

        confirmation = ProfileConfirmation(
            status=ConfirmationStatus.PENDING,
            confirmation_required=len(change_items) > 0,
            changes=change_items,
            raw_patch=patch.changes,
        )
        return confirmation

    @staticmethod
    def apply_confirmation(
        confirmation: ProfileConfirmation, state: AgentState
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Applies a confirmed patch to the AgentState.
        
        Returns:
            (updated_profile, eligibility_was_invalidated)
        """
        if confirmation.status != ConfirmationStatus.CONFIRMED:
            confirmation.status = ConfirmationStatus.CONFIRMED

        patch = ProfilePatch(changes=confirmation.raw_patch)
        old_fingerprint = ProfilePatcher.compute_fingerprint(state.profile)

        # Apply patch to confirmed profile
        new_profile = ProfilePatcher.apply_patch(state.profile, patch)
        state.profile = new_profile

        new_fingerprint = ProfilePatcher.compute_fingerprint(state.profile)
        profile_changed = (old_fingerprint != new_fingerprint)

        # Invalidate eligibility if profile changed and eligibility was previously evaluated
        eligibility_invalidated = False
        has_eval_results = len(state.eligible_schemes) > 0 or len(state.eliminated_schemes) > 0
        if profile_changed and has_eval_results:
            logger.info("Confirmed profile changed after eligibility was evaluated. Marking eligibility results STALE.")
            state.eligible_schemes = []
            state.eliminated_schemes = []
            state.stage = StageEnum.ELIGIBILITY_READY.value
            eligibility_invalidated = True

        # Reconcile contradictions if any were resolved
        for c in state.contradictions:
            if c.field in patch.changes and not c.resolved:
                c.resolved = True

        # Clear pending confirmation from state
        state.pending_confirmation = None

        # Record observability event
        confirmed_fields = list(patch.changes.keys())
        state.conversation_history.append({
            "speaker": "system",
            "event": "PROFILE_CONFIRMATION",
            "fields_confirmed": confirmed_fields,
            "profile_fingerprint": new_fingerprint,
        })

        return new_profile, eligibility_invalidated

    @staticmethod
    def reject_confirmation(
        confirmation: ProfileConfirmation, state: AgentState
    ) -> None:
        """
        Rejects a proposed patch.
        Confirmed profile remains completely unchanged!
        No proposed facts leak into eligibility.
        """
        confirmation.status = ConfirmationStatus.REJECTED
        state.pending_confirmation = None

        state.conversation_history.append({
            "speaker": "system",
            "event": "PROFILE_REJECTION",
            "rejected_fields": list(confirmation.raw_patch.keys()),
        })
