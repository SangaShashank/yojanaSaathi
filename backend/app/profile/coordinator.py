"""
Yojana Saathi - Profile Service Coordinator
===========================================
Unified backend entry points for:
- Natural-language user statements, answers, and corrections
- Human / CSC confirmation and rejection
- Direct manual field editing
- Synchronization with AgentState and recomputing gaps
"""

import logging
from typing import Any, Dict, List, Optional
from backend.app.agent.state import AgentState, Contradiction, StageEnum
from backend.app.profile.confirmation import ConfirmationManager
from backend.app.profile.extractor import ProfileExtractor
from backend.app.profile.patcher import ProfilePatcher
from backend.app.profile.schemas import (
    ConfirmationStatus,
    ProfileConfirmation,
    ProfilePatch,
    SUPPORTED_PROFILE_FIELDS,
)

logger = logging.getLogger(__name__)


class ProfileCoordinator:
    """
    Coordinates extraction, patch validation, confirmation, and state synchronization.
    """

    def __init__(self, extractor: Optional[ProfileExtractor] = None):
        self.extractor = extractor or ProfileExtractor()

    def process_user_message(
        self, state: AgentState, message: str
    ) -> Dict[str, Any]:
        """
        Processes an incoming user message:
        1. Checks for direct confirmation / rejection keywords if awaiting confirmation.
        2. Otherwise extracts structured facts.
        3. Creates a pending confirmation if facts are detected.
        4. Maintains conversation context.
        """
        clean_msg = message.strip()
        lower_msg = clean_msg.lower()

        # Record message in conversation history
        state.conversation_history.append({
            "speaker": "user",
            "text": clean_msg,
            "iteration": state.iteration,
        })

        # 1. Direct confirmation routing if pending confirmation is active
        if state.pending_confirmation:
            if lower_msg in ["confirm", "yes", "i confirm", "correct", "confirm changes", "looks good", "ok", "proceed"]:
                return self.confirm_pending_profile(state)
            elif lower_msg in ["reject", "no", "cancel", "discard", "reject changes"]:
                return self.reject_pending_profile(state)

        # 2. Extract structured profile facts using extractor
        extraction = self.extractor.extract(
            text=clean_msg,
            current_profile=state.profile,
            unresolved_fields=state.missing_information,
            conversation_context=state.conversation_history,
        )

        # Track ambiguous fields
        if extraction.ambiguous_fields:
            for f in extraction.ambiguous_fields:
                if f not in state.uncertain_fields:
                    state.uncertain_fields.append(f)

        # 3. If facts were extracted, create a field-level patch & pending confirmation
        if extraction.changes:
            patch = ProfilePatcher.create_patch(extraction.changes)
            confirmation = ConfirmationManager.create_pending_confirmation(
                current_profile=state.profile, patch=patch
            )

            # Detect contradictions
            contradictions = ProfilePatcher.detect_contradictions(state.profile, patch)
            for c in contradictions:
                state.contradictions.append(
                    Contradiction(
                        field=c["field"],
                        existing_value=c["existing_value"],
                        conflicting_value=c["proposed_value"],
                        source_turn_current=state.iteration,
                    )
                )

            # Store pending confirmation in state
            state.pending_confirmation = confirmation.model_dump()
            state.stage = StageEnum.WAITING_FOR_PROFILE_CONFIRMATION.value

            return {
                "status": "CONFIRMATION_REQUIRED",
                "confirmation_required": True,
                "confirmation_id": confirmation.confirmation_id,
                "changes": [c.model_dump() for c in confirmation.changes],
                "ambiguous_fields": extraction.ambiguous_fields,
                "needs_confirmation": True,
            }

        # 4. If only ambiguity or no facts found
        if extraction.ambiguous_fields:
            return {
                "status": "AMBIGUOUS_INPUT",
                "confirmation_required": False,
                "ambiguous_fields": extraction.ambiguous_fields,
                "message": f"Could not determine exact value for {extraction.ambiguous_fields}. Please clarify.",
            }

        return {
            "status": "NO_FACTS_EXTRACTED",
            "confirmation_required": False,
            "ambiguous_fields": [],
            "message": "No profile facts detected in input.",
        }

    def confirm_pending_profile(self, state: AgentState) -> Dict[str, Any]:
        """
        Authoritatively confirms and applies the pending patch to the citizen profile.
        Triggers missing info recalculation and marks eligibility stale if applicable.
        """
        if not state.pending_confirmation:
            return {
                "status": "ERROR",
                "message": "No pending profile confirmation exists.",
            }

        conf_data = state.pending_confirmation
        confirmation = ProfileConfirmation.model_validate(conf_data)

        updated_profile, eligibility_invalidated = ConfirmationManager.apply_confirmation(
            confirmation, state
        )

        # Recompute remaining missing fields against candidate schemes
        missing = state.recompute_missing_information()

        # Update stage based on completeness
        if len(missing) == 0 and len(state.candidate_schemes) > 0:
            state.stage = StageEnum.ELIGIBILITY_READY.value
        else:
            state.stage = StageEnum.PROFILE_CONFIRMED.value

        return {
            "status": "CONFIRMED",
            "confirmed_profile": updated_profile,
            "missing_information": missing,
            "stage": state.stage,
            "eligibility_invalidated": eligibility_invalidated,
            "message": "Profile changes confirmed and applied.",
        }

    def reject_pending_profile(self, state: AgentState) -> Dict[str, Any]:
        """
        Rejects the pending patch. Confirmed profile remains completely untouched.
        """
        if not state.pending_confirmation:
            return {
                "status": "ERROR",
                "message": "No pending profile confirmation exists.",
            }

        conf_data = state.pending_confirmation
        confirmation = ProfileConfirmation.model_validate(conf_data)

        ConfirmationManager.reject_confirmation(confirmation, state)
        state.stage = StageEnum.INTAKE.value if not state.profile else StageEnum.MISSING_INFO_COLLECTION.value

        return {
            "status": "REJECTED",
            "confirmed_profile": state.profile,
            "message": "Proposed profile changes rejected. Confirmed profile unchanged.",
        }

    def apply_manual_edit(
        self,
        state: AgentState,
        field: str,
        value: Any,
        auto_confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Supports direct manual field editing independently of Gemini.
        Converges on the exact same ProfilePatch and confirmation mechanism.
        """
        if field not in SUPPORTED_PROFILE_FIELDS:
            raise ValueError(f"Field '{field}' is not supported in CitizenProfile schema.")

        patch = ProfilePatcher.create_patch({field: value})
        confirmation = ConfirmationManager.create_pending_confirmation(
            current_profile=state.profile, patch=patch
        )

        if auto_confirm:
            # Immediate confirmation for direct authorized edits
            confirmation.status = ConfirmationStatus.CONFIRMED
            updated_profile, eligibility_invalidated = ConfirmationManager.apply_confirmation(
                confirmation, state
            )
            state.recompute_missing_information()
            return {
                "status": "CONFIRMED",
                "confirmed_profile": updated_profile,
                "eligibility_invalidated": eligibility_invalidated,
            }

        # Otherwise stage for confirmation
        state.pending_confirmation = confirmation.model_dump()
        state.stage = StageEnum.WAITING_FOR_PROFILE_CONFIRMATION.value

        return {
            "status": "CONFIRMATION_REQUIRED",
            "confirmation_required": True,
            "confirmation_id": confirmation.confirmation_id,
            "changes": [c.model_dump() for c in confirmation.changes],
        }


# Convenience module-level functions
_default_coordinator = ProfileCoordinator()


def process_user_message(state: AgentState, message: str) -> Dict[str, Any]:
    return _default_coordinator.process_user_message(state, message)


def confirm_pending_profile(state: AgentState) -> Dict[str, Any]:
    return _default_coordinator.confirm_pending_profile(state)


def reject_pending_profile(state: AgentState) -> Dict[str, Any]:
    return _default_coordinator.reject_pending_profile(state)


def apply_manual_edit(
    state: AgentState, field: str, value: Any, auto_confirm: bool = False
) -> Dict[str, Any]:
    return _default_coordinator.apply_manual_edit(state, field, value, auto_confirm=auto_confirm)
