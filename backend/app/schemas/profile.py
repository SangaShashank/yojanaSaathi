"""
Yojana Saathi - Citizen Profile Schema
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


UNKNOWN_SENTINEL = "UNKNOWN"

# Canonical field aliases mapping target field to list of alternate field names
FIELD_ALIASES: Dict[str, list[str]] = {
    "land_acres": ["land_holding_acres", "land_acres"],
    "land_holding_acres": ["land_acres", "land_holding_acres"],
    "annual_income_inr": ["annual_family_income_inr", "annual_income_inr"],
    "annual_family_income_inr": ["annual_income_inr", "annual_family_income_inr"],
    "occupation": ["occupation_type", "occupation"],
    "occupation_type": ["occupation", "occupation_type"],
}


class CitizenProfile(BaseModel):
    """
    Confirmed citizen profile model.
    Contains confirmed attributes of a citizen for deterministic eligibility checks.
    Additional attributes are permitted via extra='allow'.
    """
    model_config = ConfigDict(extra="allow")

    # Common demographic fields
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    residence_type: Optional[str] = None  # e.g., 'rural', 'urban'
    community: Optional[str] = None       # e.g., 'sc_st', 'bc_ebc', 'minority', 'general'
    is_bpl: Optional[bool] = None

    # Occupation / Farmer specific fields
    occupation: Optional[str] = None
    occupation_type: Optional[str] = None
    land_ownership: Optional[bool] = None
    land_acres: Optional[float] = None
    land_holding_acres: Optional[float] = None
    land_record_date: Optional[str] = None  # Format: YYYY-MM-DD
    active_cultivation_status: Optional[bool] = None
    cultivates_land: Optional[bool] = None
    farmer_id_status: Optional[str] = None
    land_verification_source: Optional[str] = None
    cultivates_notified_crop: Optional[bool] = None
    crop_season: Optional[str] = None
    land_or_tenancy_status: Optional[str] = None
    enrollment_type: Optional[str] = None

    # Financial
    annual_income_inr: Optional[float] = None
    annual_family_income_inr: Optional[float] = None

    # Family / Marital / Vulnerability
    marriage_status: Optional[str] = None
    groom_age: Optional[int] = None
    pregnancy_or_lactation_status: Optional[bool] = None
    registration_days_after_lmp: Optional[int] = None
    delivery_location_type: Optional[str] = None
    category: Optional[str] = None
    widow_status: Optional[bool] = None
    facing_violence_or_abuse_flag: Optional[bool] = None
    girl_child_age: Optional[int] = None
    existing_ssy_accounts_count: Optional[int] = None
    co_borrower_legal_heir: Optional[bool] = None

    def get_field_value(self, field_name: str) -> tuple[Any, bool]:
        """
        Retrieves a field's value and whether it is known.
        
        Returns:
            (value, is_known):
            - If known: (value, True)
            - If unknown/missing: (None, False)
        """
        # 1. Direct attribute or dictionary lookup
        raw_dict = self.model_dump()

        candidates = [field_name]
        if field_name in FIELD_ALIASES:
            candidates.extend(FIELD_ALIASES[field_name])

        for candidate in candidates:
            if candidate in raw_dict:
                val = raw_dict[candidate]
                if val is not None and val != UNKNOWN_SENTINEL and val != "unknown":
                    return val, True

        # 2. Derived rules (e.g. land_ownership from land_acres)
        if field_name == "land_ownership":
            acres, has_acres = self.get_field_value("land_acres")
            if has_acres and acres is not None:
                return (acres > 0), True

        return None, False

    def is_field_known(self, field_name: str) -> bool:
        """Checks if a field is explicitly known."""
        _, is_known = self.get_field_value(field_name)
        return is_known
