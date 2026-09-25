"""
Yojana Saathi - Deterministic Profile Normalizer
================================================
Deterministic normalization rules for profile facts extracted from natural language or forms.
Handles:
- Indian currency normalization (Lakhs, Thousands, Crores, ₹ / Rs symbols)
- Land measurement normalization (acres, ac, hectares)
- Age normalization
- Canonical categorical mappings (occupation, state, gender, marital status)
- Strict ambiguity detection (numbers without units or vague contexts)
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# Known canonical Indian States and UTs
KNOWN_STATES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    "delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
}

# Permitted occupation canonical mappings
OCCUPATION_MAP = {
    "farmer": "farmer",
    "farming": "farmer",
    "agriculture": "farmer",
    "agriculturist": "farmer",
    "cultivator": "farmer",
    "kisan": "farmer",
    "rythu": "farmer",
    "laborer": "laborer",
    "labourer": "laborer",
    "agricultural labourer": "agricultural_laborer",
    "agricultural laborer": "agricultural_laborer",
    "daily wage worker": "daily_wage_worker",
    "artisan": "artisan",
    "weaver": "weaver",
    "student": "student",
    "unemployed": "unemployed",
}

# Canonical gender mappings
GENDER_MAP = {
    "male": "male",
    "m": "male",
    "man": "male",
    "boy": "male",
    "female": "female",
    "f": "female",
    "woman": "female",
    "girl": "female",
    "transgender": "transgender",
    "other": "other",
}


def normalize_income(val: Any) -> Tuple[Optional[float], bool]:
    """
    Normalizes annual income representation to numeric INR.
    
    Examples:
        "₹2 lakh" -> (200000.0, False)
        "2 lakh" -> (200000.0, False)
        "Rs. 2,00,000" -> (200000.0, False)
        "1.8 lakh" -> (180000.0, False)
        "about two" -> (None, True)  # Ambiguous
    
    Returns:
        (normalized_value, is_ambiguous)
    """
    if val is None:
        return None, False

    if isinstance(val, (int, float)):
        if val < 0:
            return None, False
        # Direct small number like 2 or 5 without lakh/k could be ambiguous
        if 0 < val <= 20:
            return None, True
        return float(val), False

    s = str(val).strip().lower()

    # Clean currency symbols
    s = s.replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "").replace(",", "").strip()

    # Check for ambiguous vague phrases like "about two", "two", "around 2" without unit
    vague_number_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    for word, num in vague_number_words.items():
        if re.search(rf"\b(about|around|approx|nearly)?\s*{word}\b", s) and not any(u in s for u in ["lakh", "lac", "crore", "thousand", "k"]):
            return None, True

    # Check for Crore
    crore_match = re.search(r"([\d\.]+)\s*(?:crore|cr)", s)
    if crore_match:
        try:
            return float(crore_match.group(1)) * 10000000.0, False
        except ValueError:
            return None, True

    # Check for Lakh
    lakh_match = re.search(r"([\d\.]+)\s*(?:lakh|lakhs|lac|lacs|l)", s)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0, False
        except ValueError:
            return None, True

    # Check for Thousand / k
    thousand_match = re.search(r"([\d\.]+)\s*(?:thousand|thousands|k)", s)
    if thousand_match:
        try:
            return float(thousand_match.group(1)) * 1000.0, False
        except ValueError:
            return None, True

    # Raw digits (e.g. "200000")
    pure_num_match = re.search(r"^[\d\.]+$", s)
    if pure_num_match:
        try:
            num = float(s)
            # If someone entered "2" as income without units, that is ambiguous
            if 0 < num <= 20:
                return None, True
            return num, False
        except ValueError:
            return None, True

    return None, True


def normalize_land_acres(val: Any) -> Tuple[Optional[float], bool]:
    """
    Normalizes land holding to acres.
    
    Examples:
        "3 acres" -> (3.0, False)
        "3 acre" -> (3.0, False)
        "3 ac" -> (3.0, False)
        "5.5 acres" -> (5.5, False)
        3 -> (3.0, False)
    
    Returns:
        (normalized_value, is_ambiguous)
    """
    if val is None:
        return None, False

    if isinstance(val, (int, float)):
        if val < 0:
            return None, False
        return float(val), False

    s = str(val).strip().lower()

    # Ambiguous phrases like "I have five" without land/acre unit
    if re.search(r"^(?:about|around|approx)?\s*(?:five|four|three|two|one|six|seven|eight|ten)\s*$", s):
        return None, True

    # Match acres / ac / acre
    acre_match = re.search(r"([\d\.]+)\s*(?:acres?|ac\b|ekad|ekars?)", s)
    if acre_match:
        try:
            return float(acre_match.group(1)), False
        except ValueError:
            return None, True

    # Match hectares (1 hectare = 2.47105 acres)
    hec_match = re.search(r"([\d\.]+)\s*(?:hectares?|ha\b)", s)
    if hec_match:
        try:
            return round(float(hec_match.group(1)) * 2.47105, 2), False
        except ValueError:
            return None, True

    # Raw numeric
    try:
        num = float(s)
        if num >= 0:
            return num, False
    except ValueError:
        pass

    return None, True


def normalize_age(val: Any) -> Tuple[Optional[int], bool]:
    """
    Normalizes citizen age.
    Valid range: 0 to 125.
    """
    if val is None:
        return None, False

    if isinstance(val, int):
        if 0 <= val <= 125:
            return val, False
        return None, False

    if isinstance(val, float):
        ival = int(val)
        if 0 <= ival <= 125:
            return ival, False
        return None, False

    s = str(val).strip().lower()
    match = re.search(r"(\d{1,3})\s*(?:years?|yrs?|yr|age)?", s)
    if match:
        try:
            age = int(match.group(1))
            if 0 <= age <= 125:
                return age, False
        except ValueError:
            pass

    return None, True


def normalize_state(val: Any) -> Tuple[Optional[str], bool]:
    """
    Normalizes state name to canonical form if known.
    """
    if not val:
        return None, False

    s = str(val).strip().lower()
    if s in KNOWN_STATES:
        return KNOWN_STATES[s], False

    # Title-case fallback if string
    cleaned = str(val).strip().title()
    return cleaned, False


def normalize_occupation(val: Any) -> Tuple[Optional[str], bool]:
    """
    Normalizes occupation to supported canonical domain values.
    """
    if not val:
        return None, False

    s = str(val).strip().lower()
    if s in OCCUPATION_MAP:
        return OCCUPATION_MAP[s], False

    return s, False


def normalize_boolean(val: Any) -> Tuple[Optional[bool], bool]:
    """
    Normalizes boolean facts.
    """
    if val is None:
        return None, False

    if isinstance(val, bool):
        return val, False

    s = str(val).strip().lower()
    if s in ["true", "yes", "y", "1"]:
        return True, False
    if s in ["false", "no", "n", "0"]:
        return False, False

    return None, True


def normalize_field(field_name: str, value: Any) -> Tuple[Any, bool]:
    """
    Dispatches normalization for a specific CitizenProfile field.
    
    Returns:
        (normalized_value, is_ambiguous)
    """
    if value is None:
        return None, False

    if field_name in ["annual_income_inr", "annual_family_income_inr"]:
        return normalize_income(value)

    if field_name in ["land_acres", "land_holding_acres"]:
        return normalize_land_acres(value)

    if field_name in ["age", "groom_age", "girl_child_age"]:
        return normalize_age(value)

    if field_name == "state":
        return normalize_state(value)

    if field_name in ["occupation", "occupation_type"]:
        return normalize_occupation(value)

    if field_name == "gender":
        s = str(value).strip().lower()
        if s in GENDER_MAP:
            return GENDER_MAP[s], False
        return s, False

    if field_name in [
        "is_bpl",
        "land_ownership",
        "active_cultivation_status",
        "cultivates_land",
        "cultivates_notified_crop",
        "widow_status",
        "pregnancy_or_lactation_status",
        "facing_violence_or_abuse_flag",
        "co_borrower_legal_heir",
    ]:
        return normalize_boolean(value)

    # For other string fields, clean whitespace
    if isinstance(value, str):
        return value.strip(), False

    return value, False
