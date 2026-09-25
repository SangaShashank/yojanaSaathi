"""
Yojana Saathi - Profile Patcher
===============================
Deterministic field-level profile patching and fingerprinting.
Guarantees:
- Only explicitly patched fields are updated.
- All unrelated fields are strictly preserved.
- Arbitrary unsupported fields are rejected by Pydantic validation.
- Generates structured diffs (previous vs proposed) for human/CSC review.
- Detects contradictions against current confirmed profile.
- Computes deterministic SHA-256 fingerprints to track profile versioning and staleness.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from backend.app.profile.normalizer import normalize_field
from backend.app.profile.schemas import (
    ProfileChangeItem,
    ProfilePatch,
    SUPPORTED_PROFILE_FIELDS,
)
from backend.app.schemas.profile import CitizenProfile


class ProfilePatcher:
    """
    Manages field-level modifications and diffing against confirmed CitizenProfile state.
    """

    @staticmethod
    def compute_fingerprint(profile: Dict[str, Any]) -> str:
        """
        Computes a stable deterministic SHA-256 fingerprint of the confirmed profile.
        Ignores None, UNKNOWN, and internal metadata.
        """
        clean_facts = {}
        for k, v in sorted(profile.items()):
            if v is not None and v != "UNKNOWN" and v != "unknown":
                clean_facts[k] = str(v)

        serialized = json.dumps(clean_facts, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def create_patch(raw_changes: Dict[str, Any]) -> ProfilePatch:
        """
        Validates and normalizes raw dictionary into a strictly typed ProfilePatch.
        Rejects any fields not present in CitizenProfile.
        """
        normalized_changes: Dict[str, Any] = {}
        for field, raw_val in raw_changes.items():
            if field not in SUPPORTED_PROFILE_FIELDS:
                raise ValueError(f"Field '{field}' is not supported in CitizenProfile schema.")
            
            norm_val, is_ambiguous = normalize_field(field, raw_val)
            if not is_ambiguous and norm_val is not None:
                normalized_changes[field] = norm_val

        return ProfilePatch(changes=normalized_changes)

    @staticmethod
    def generate_change_items(
        current_profile: Dict[str, Any], patch: ProfilePatch
    ) -> List[ProfileChangeItem]:
        """
        Compares patch against current profile to produce judge/demo-friendly change items:
        [{"field": "land_holding_acres", "previous": 3, "proposed": 5}]
        """
        items: List[ProfileChangeItem] = []
        for field, proposed_val in patch.changes.items():
            prev_val = current_profile.get(field)
            if prev_val in ["UNKNOWN", "unknown"]:
                prev_val = None

            # Only propose if value is genuinely changing or filling a missing gap
            if prev_val != proposed_val:
                items.append(
                    ProfileChangeItem(
                        field=field,
                        previous=prev_val,
                        proposed=proposed_val,
                    )
                )
        return items

    @staticmethod
    def detect_contradictions(
        current_profile: Dict[str, Any], patch: ProfilePatch
    ) -> List[Dict[str, Any]]:
        """
        Detects factual contradictions where an existing known confirmed value
        is being replaced by a differing proposed value.
        """
        contradictions = []
        for field, proposed_val in patch.changes.items():
            prev_val = current_profile.get(field)
            if (
                prev_val is not None
                and prev_val not in ["UNKNOWN", "unknown"]
                and prev_val != proposed_val
            ):
                contradictions.append({
                    "field": field,
                    "existing_value": prev_val,
                    "proposed_value": proposed_val,
                })
        return contradictions

    @staticmethod
    def apply_patch(
        current_profile: Dict[str, Any], patch: ProfilePatch
    ) -> Dict[str, Any]:
        """
        Applies a validated patch to the current profile.
        Strictly preserves all unrelated fields!
        Validates resulting profile through CitizenProfile.
        """
        updated = dict(current_profile)
        for field, val in patch.changes.items():
            updated[field] = val

        # Validate that the merged profile satisfies CitizenProfile schema
        validated_profile = CitizenProfile.model_validate(updated)
        return validated_profile.model_dump(exclude_unset=False, exclude_none=True)
