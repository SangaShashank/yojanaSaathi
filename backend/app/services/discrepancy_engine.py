"""
Yojana Saathi - Document vs Profile Discrepancy Engine
=====================================================
Compares extracted document facts against the authoritative confirmed profile.
Surfaces discrepancies without auto-rejecting the citizen.
Enforces that document extraction NEVER directly mutates the confirmed profile.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.app.schemas.document import (
    DiscrepancyStatus,
    DiscrepancyType,
    DocumentDiscrepancyItem,
)


logger = logging.getLogger(__name__)


def normalize_text_for_comparison(val: Any) -> str:
    """Normalizes string for comparison (lowercased, stripped, condensed whitespace, no punctuation)."""
    if val is None:
        return ""
    text = str(val).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compare_field_values(
    field_name: str,
    profile_value: Any,
    document_value: Any,
) -> Tuple[bool, Optional[str]]:
    """
    Compares profile value with document value for a specific field.
    Returns: (is_match, discrepancy_type)
    - If document value is missing/None -> (True, None) because unknown is NOT a mismatch.
    - If values match after normalization -> (True, None).
    - If values mismatch -> (False, DiscrepancyType).
    """
    # Rule: Unknown document values remain unknown and are NOT treated as mismatches.
    if document_value is None or document_value == "":
        return True, None

    # If profile value is None, document provides new unconfirmed info, not a contradiction
    if profile_value is None:
        return True, None

    # 1. Numeric Fields (land, income, age)
    if field_name in ["land_holding_acres", "land_acres", "annual_income_inr", "age"]:
        try:
            p_num = float(profile_value)
            d_num = float(document_value)
            if abs(p_num - d_num) < 0.01:
                return True, None
            else:
                return False, DiscrepancyType.VALUE_MISMATCH.value
        except (ValueError, TypeError):
            return False, DiscrepancyType.VALUE_MISMATCH.value

    # 2. Name / Identity Fields
    if field_name == "name":
        p_name = normalize_text_for_comparison(profile_value)
        d_name = normalize_text_for_comparison(document_value)
        if p_name == d_name:
            return True, None

        # Check token subset match (e.g. "Ramulu Goud" vs "Goud Ramulu")
        p_tokens = set(p_name.split())
        d_tokens = set(d_name.split())
        if p_tokens == d_tokens or (len(p_tokens) > 1 and p_tokens.issubset(d_tokens)):
            return True, None

        return False, DiscrepancyType.IDENTITY_MISMATCH.value

    # 3. Categorical / General string fields (state, district, farmer_id_status)
    p_str = normalize_text_for_comparison(profile_value)
    d_str = normalize_text_for_comparison(document_value)
    if p_str == d_str:
        return True, None

    return False, DiscrepancyType.VALUE_MISMATCH.value


class DiscrepancyEngine:
    """Compares document data with citizen profile and surfaces discrepancies."""

    @classmethod
    def compare_document_with_profile(
        cls,
        document_id: str,
        application_id: Optional[str],
        extracted_data: Dict[str, Any],
        profile_data: Dict[str, Any],
        verification_fields: List[str],
    ) -> List[DocumentDiscrepancyItem]:
        """
        Deterministic comparison across all designated verification fields.
        Returns a list of detected discrepancies.
        """
        discrepancies: List[DocumentDiscrepancyItem] = []

        # Alias resolution helper
        def get_profile_val(f_name: str) -> Any:
            if f_name in profile_data:
                return profile_data[f_name]
            if f_name == "land_holding_acres" and "land_acres" in profile_data:
                return profile_data["land_acres"]
            if f_name == "land_acres" and "land_holding_acres" in profile_data:
                return profile_data["land_holding_acres"]
            return None

        for field in verification_fields:
            # Check if field or alias is in extracted data
            doc_val = extracted_data.get(field)
            if doc_val is None:
                if field == "land_holding_acres":
                    doc_val = extracted_data.get("land_acres")
                elif field == "land_acres":
                    doc_val = extracted_data.get("land_holding_acres")

            if doc_val is None:
                continue

            prof_val = get_profile_val(field)
            is_match, disc_type = compare_field_values(field, prof_val, doc_val)

            if not is_match and disc_type:
                import uuid
                discrepancies.append(
                    DocumentDiscrepancyItem(
                        discrepancy_id=f"disc_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        application_id=application_id,
                        field_name=field,
                        profile_value=prof_val,
                        document_value=doc_val,
                        discrepancy_type=disc_type,
                        status=DiscrepancyStatus.OPEN.value,
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

        return discrepancies
