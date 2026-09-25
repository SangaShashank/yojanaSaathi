"""
Yojana Saathi - Profile Management Package
==========================================
Phase 3 components for:
- Profile Fact Extraction (Gemini + Deterministic Fallback)
- Deterministic Normalization & Ambiguity Detection
- Field-level Profile Patches & Fingerprints
- Human / CSC Confirmation Lifecycle
- Profile Service Coordination & AgentState Synchronization
"""

from backend.app.profile.confirmation import ConfirmationManager
from backend.app.profile.coordinator import (
    ProfileCoordinator,
    apply_manual_edit,
    confirm_pending_profile,
    process_user_message,
    reject_pending_profile,
)
from backend.app.profile.extractor import ProfileExtractor
from backend.app.profile.normalizer import (
    normalize_age,
    normalize_field,
    normalize_income,
    normalize_land_acres,
    normalize_state,
)
from backend.app.profile.patcher import ProfilePatcher
from backend.app.profile.schemas import (
    ConfirmationStatus,
    ProfileActivityEvent,
    ProfileChangeItem,
    ProfileConfirmation,
    ProfileExtractionResult,
    ProfilePatch,
)

__all__ = [
    "ConfirmationManager",
    "ConfirmationStatus",
    "ProfileActivityEvent",
    "ProfileChangeItem",
    "ProfileConfirmation",
    "ProfileCoordinator",
    "ProfileExtractionResult",
    "ProfileExtractor",
    "ProfilePatch",
    "ProfilePatcher",
    "apply_manual_edit",
    "confirm_pending_profile",
    "normalize_age",
    "normalize_field",
    "normalize_income",
    "normalize_land_acres",
    "normalize_state",
    "process_user_message",
    "reject_pending_profile",
]
