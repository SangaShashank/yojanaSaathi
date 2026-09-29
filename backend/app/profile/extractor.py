"""
Yojana Saathi - Profile Fact Extractor
======================================
Converts natural-language citizen messages into structured profile facts.
Integrates Gemini with strict structured Pydantic output, bounded retries,
and a deterministic regex/rule-based fallback for offline and test operation.

Guarantees:
- Only explicitly stated facts are extracted.
- Missing fields strictly remain UNKNOWN.
- Zero hallucination / no guessing of unstated attributes.
- Ambiguous claims without units trigger ambiguity flags.
- Prompt injection attempts cannot redefine rules or force eligibility.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from backend.app.profile.normalizer import (
    GENDER_MAP,
    KNOWN_STATES,
    OCCUPATION_MAP,
    normalize_age,
    normalize_field,
    normalize_income,
    normalize_land_acres,
    normalize_state,
)
from backend.app.profile.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    format_extraction_prompt,
)
from backend.app.profile.schemas import (
    SUPPORTED_PROFILE_FIELDS,
    ProfileExtractionResult,
)

logger = logging.getLogger(__name__)


class ProfileExtractor:
    """
    Extracts structured CitizenProfile facts from natural language text.
    Uses Gemini when configured with fallback to deterministic pattern matching.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        use_llm: bool = True,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.use_llm = use_llm and bool(self.api_key)
        self._client = None

        if self.use_llm:
            try:
                import google.genai as genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client for ProfileExtractor: {e}. Using deterministic engine.")
                self.use_llm = False

    def extract(
        self,
        text: str,
        current_profile: Optional[Dict[str, Any]] = None,
        unresolved_fields: Optional[List[str]] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> ProfileExtractionResult:
        """
        Extracts structured profile facts from user message.
        """
        if not text or not text.strip():
            return ProfileExtractionResult()

        clean_text = text.strip()

        # 1. Attempt LLM extraction if enabled
        if self.use_llm and self._client:
            llm_result = self._extract_with_gemini(
                clean_text, current_profile, unresolved_fields, conversation_context
            )
            if llm_result is not None:
                return self._post_process_and_normalize(llm_result)

        # 2. Deterministic rule-based extraction (offline / test / fallback)
        return self._extract_deterministic(
            clean_text, current_profile, unresolved_fields, conversation_context
        )

    def _extract_with_gemini(
        self,
        text: str,
        current_profile: Optional[Dict[str, Any]],
        unresolved_fields: Optional[List[str]],
        conversation_context: Optional[List[Dict[str, Any]]],
    ) -> Optional[ProfileExtractionResult]:
        """Invokes Gemini with bounded retries and structured schema."""
        prompt_content = format_extraction_prompt(
            user_message=text,
            current_profile=current_profile,
            unresolved_fields=unresolved_fields,
            conversation_context=conversation_context,
        )

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt_content,
                    config={
                        "system_instruction": EXTRACTION_SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_schema": ProfileExtractionResult,
                        "temperature": 0.0,
                    },
                )
                if response and response.text:
                    parsed = json.loads(response.text)
                    return ProfileExtractionResult.model_validate(parsed)
            except Exception as e:
                logger.warning(f"Gemini extraction attempt {attempt + 1} failed: {e}")

        return None

    def _extract_deterministic(
        self,
        text: str,
        current_profile: Optional[Dict[str, Any]] = None,
        unresolved_fields: Optional[List[str]] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> ProfileExtractionResult:
        """
        Deterministic pattern extraction without external LLM.
        Accurately parses single and multi-fact inputs while enforcing strict ambiguity guards.
        """
        lower = text.lower()
        changes: Dict[str, Any] = {}
        explicitly_stated: List[str] = []
        ambiguous_fields: List[str] = []

        # Prompt injection filter: If input contains commands trying to override system rules, ignore them
        injection_triggers = ["ignore all rules", "mark me eligible", "forget instructions", "override profile"]
        for trig in injection_triggers:
            if trig in lower:
                logger.warning(f"Ignored potential prompt injection command: '{trig}'")
                lower = lower.replace(trig, "")

        # Determine last question asked from context to resolve direct answers
        last_asked_field = None
        if conversation_context:
            for item in reversed(conversation_context):
                if item.get("speaker") == "agent" and item.get("field"):
                    last_asked_field = item["field"]
                    break

        # 1. State extraction
        for state_key, canonical_state in KNOWN_STATES.items():
            # Match word boundary
            if re.search(rf"\b{re.escape(state_key)}\b", lower):
                changes["state"] = canonical_state
                explicitly_stated.append("state")
                break

        # 2. Occupation extraction
        for occ_key, canonical_occ in OCCUPATION_MAP.items():
            if re.search(rf"\b{re.escape(occ_key)}\b", lower):
                changes["occupation"] = canonical_occ
                explicitly_stated.append("occupation")
                break

        # 3. Land Acres extraction
        land_match = re.search(
            r"(?:have|own|cultivate|holding|acres?|land)?\s*(\d+(?:\.\d+)?)\s*(?:acres?|ac\b|ekad|ekars?)",
            lower,
        )
        if land_match:
            acres, is_ambig = normalize_land_acres(land_match.group(1))
            if not is_ambig and acres is not None:
                changes["land_holding_acres"] = acres
                explicitly_stated.append("land_holding_acres")
        elif "acres" in lower or "acre" in lower:
            # Check for direct number near acre
            m = re.search(r"(\d+(?:\.\d+)?)\s*acres?", lower)
            if m:
                acres, _ = normalize_land_acres(m.group(1))
                if acres is not None:
                    changes["land_holding_acres"] = acres
                    explicitly_stated.append("land_holding_acres")

        # 4. Income extraction
        # Match explicit income mentions: "income is 2 lakh", "earn 1.8 lakh", "Rs 200000", "₹2,00,000"
        income_match = re.search(
            r"(?:income|earn|earning|salary|revenue|family income)\s*(?:is|of|about|around|approx)?\s*(?:₹|rs\.?|inr)?\s*([\d\.]+(?:\s*(?:lakhs?|lac|crore|thousand|k))?)",
            lower,
        )
        if income_match:
            inc_val, is_ambig = normalize_income(income_match.group(1))
            if is_ambig:
                ambiguous_fields.append("annual_income_inr")
            elif inc_val is not None:
                changes["annual_income_inr"] = inc_val
                explicitly_stated.append("annual_income_inr")
        else:
            # Check if user says e.g. "earn 2 lakh" or "earn about two"
            earn_vague = re.search(r"\b(?:earn|income)\s*(?:is|about|around)?\s*(?:two|three|four|five|one|ten)\b", lower)
            if earn_vague and "lakh" not in lower and "thousand" not in lower:
                ambiguous_fields.append("annual_income_inr")
            else:
                # Standalone lakh mention like "earn 2 lakh" or "and earn 2 lakh"
                lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*([\d\.]+)\s*(?:lakhs?|lac)", lower)
                if lakh_match:
                    inc_val, is_ambig = normalize_income(lakh_match.group(0))
                    if not is_ambig and inc_val is not None:
                        changes["annual_income_inr"] = inc_val
                        explicitly_stated.append("annual_income_inr")

        # Identify if message refers to another person (child, spouse, relative)
        third_person_pattern = r"\b(?:daughter|son|girl\s*child|child(?:ren)?|kids?|husband|wife|spouse|father|mother|sister|brother)\b"
        has_third_person = bool(re.search(third_person_pattern, lower))

        # Check for girl child age specifically (e.g. "age of my girl child is 14", "my girl child is 14")
        girl_age_match = re.search(r"\b(?:girl\s*child(?:'s)?(?:\s+age)?|daughter(?:'s)?(?:\s+age)?)\s*(?:is|:)?\s*(\d{1,2})\b", lower)
        if not girl_age_match:
            girl_age_match = re.search(r"\b(?:age\s+of\s+my\s+(?:girl\s*child|daughter))\s*(?:is|:)?\s*(\d{1,2})\b", lower)
        if girl_age_match and "girl_child_age" not in changes:
            g_age, is_g_ambig = normalize_age(girl_age_match.group(1))
            if not is_g_ambig and g_age is not None:
                changes["girl_child_age"] = g_age
                explicitly_stated.append("girl_child_age")

        # 5. Citizen Age extraction
        # e.g., "I am 42", "age is 45", "my age is 45", "42 years old", "am 42,"
        # Guard: Do not attribute third-person age (e.g., "my daughter is 14", "my husband is 42") to the citizen!
        if not has_third_person or re.search(r"\b(?:i\s+am|i'm|my\s+age)\s*(\d{1,3})\b", lower):
            age_match = re.search(
                r"\b(?:(?:my\s+)?age\s*(?:is|:)?|i am|i'm|am)\s*(\d{1,3})\b(?!\s*(?:acres?|ac|lakh|rs|k|ekad))",
                lower,
            )
            if age_match:
                age_val, is_ambig = normalize_age(age_match.group(1))
                if not is_ambig and age_val is not None:
                    changes["age"] = age_val
                    explicitly_stated.append("age")
            elif not has_third_person:
                age_explicit = re.search(r"(\d{1,3})\s*(?:years? old|yrs? old)", lower)
                if age_explicit:
                    age_val, is_ambig = normalize_age(age_explicit.group(1))
                    if not is_ambig and age_val is not None:
                        changes["age"] = age_val
                        explicitly_stated.append("age")

        # 6. Ambiguous standalone number statements: "I have five", "I have 5" (no unit specified)
        vague_have = re.search(r"\b(?:i have|have)\s+(?:five|5|four|4|three|3|two|2|ten|10)\b(?!\s*(?:acres?|ac|lakh|rs|years))", lower)
        if vague_have and "land_holding_acres" not in changes and "annual_income_inr" not in changes and "age" not in changes:
            ambiguous_fields.append("land_holding_acres")

        # 7. Gender extraction
        # Guard: Do NOT attribute another person's gender to the citizen (e.g. "my girl child is 14", "my daughter", "my husband")
        if "gender" not in changes:
            has_first_person_gender = bool(re.search(r"\b(?:i\s+am|i'm|myself)\s+(?:a\s+)?(?:female|male|woman|man|girl|boy|transgender|other)\b", lower))
            is_direct_single_word_gender = bool(re.fullmatch(r"\s*(?:male|female|m|f|man|woman|transgender|other)[.,!]?\s*", lower))

            if has_first_person_gender or is_direct_single_word_gender or not has_third_person:
                # If message contains third-person references, do not match 'girl' or 'boy' or third-person mentions as citizen gender
                filtered_gender_keys = list(GENDER_MAP.keys())
                if has_third_person:
                    filtered_gender_keys = [k for k in filtered_gender_keys if k not in ("girl", "boy")]

                for gender_key in filtered_gender_keys:
                    gender_val = GENDER_MAP[gender_key]
                    if re.search(rf"\b{re.escape(gender_key)}\b", lower):
                        # Extra check: 'girl' in 'girl child' must not trigger gender
                        if gender_key == "girl" and "girl child" in lower:
                            continue
                        changes["gender"] = gender_val
                        explicitly_stated.append("gender")
                        break

        # 8. Caste category extraction
        if "category" not in changes:
            caste_patterns = {
                r"\b(?:my category is |i am |i belong to )?(?:scheduled caste|sc)\b": "SC",
                r"\b(?:my category is |i am |i belong to )?(?:scheduled tribe|st)\b": "ST",
                r"\b(?:my category is |i am |i belong to )?(?:obc|other backward class|bc)\b": "OBC",
                r"\b(?:my category is |i am |i belong to )?(?:general|gen|unreserved)\b": "General",
            }
            for pat, caste_val in caste_patterns.items():
                if re.search(pat, lower):
                    changes["category"] = caste_val
                    explicitly_stated.append("category")
                    break

        # 9. Land ownership (boolean) extraction
        if "land_ownership" not in changes:
            if re.search(r"\b(?:yes[,.]?\s*i\s*own|i\s*own\s*(?:cultivable\s*)?(?:agricultural\s*)?land|own\s*land|land\s*owner|i\s*have\s*(?:my\s*own\s*)?land)\b", lower):
                changes["land_ownership"] = True
                explicitly_stated.append("land_ownership")
            elif re.search(r"\b(?:no[,.]?\s*(?:i\s*(?:am|do)\s*(?:not|n'?t)\s*own|tenant|landless)|i\s*(?:am|do)\s*(?:not|n'?t)\s*own\s*land|tenant\s*farmer|landless)\b", lower):
                changes["land_ownership"] = False
                explicitly_stated.append("land_ownership")

        # 10. Cultivates land (boolean) extraction
        if "cultivates_land" not in changes:
            if re.search(r"\b(?:yes[,.]?\s*i\s*(?:actively\s*)?cultivate|i\s*cultivate|i\s*do\s*(?:the\s*)?farming|actively\s*cultivat)", lower):
                changes["cultivates_land"] = True
                explicitly_stated.append("cultivates_land")
            elif re.search(r"\b(?:no[,.]?\s*i\s*do\s*(?:not|n'?t)\s*cultivat|i\s*do\s*not\s*cultivat|don'?t\s*cultivat)", lower):
                changes["cultivates_land"] = False
                explicitly_stated.append("cultivates_land")

        # 11. Residence type extraction
        if "residence_type" not in changes:
            if re.search(r"\b(?:rural|village|gram|gaon|panchayat|i\s*reside\s*in\s*a?\s*rural)", lower):
                changes["residence_type"] = "rural"
                explicitly_stated.append("residence_type")
            elif re.search(r"\b(?:urban|city|town|municipality|nagar|i\s*reside\s*in\s*a?n?\s*urban)", lower):
                changes["residence_type"] = "urban"
                explicitly_stated.append("residence_type")

        # 12. BPL status extraction (check denial first to avoid false positive on "do not have a BPL")
        if "is_bpl" not in changes:
            if re.search(r"(?:no\s*bpl|not\s*(?:a\s*)?bpl|no[,.]?\s*we\s*do\s*not\s*have|don'?t\s*have\s*(?:a\s*)?bpl|above\s*poverty\s*line|\bapl\b|not\s*have\s*(?:a\s*)?bpl)", lower):
                changes["is_bpl"] = False
                explicitly_stated.append("is_bpl")
            elif re.search(r"\b(?:yes[,.]?\s*(?:my\s*family\s*)?(?:has\s*a?\s*)?bpl|bpl\s*card\s*holder|have\s*(?:a\s*)?bpl|i\s*am\s*bpl|below\s*poverty\s*line)", lower):
                changes["is_bpl"] = True
                explicitly_stated.append("is_bpl")

        # 13. Farmer ID status extraction
        if "farmer_id_status" not in changes:
            if re.search(r"\b(?:yes[,.]?\s*i\s*have\s*(?:an?\s*)?(?:active\s*)?(?:registered\s*)?farmer\s*id|have\s*farmer\s*(?:id|card)|registered\s*farmer)\b", lower):
                changes["farmer_id_status"] = "registered"
                explicitly_stated.append("farmer_id_status")
            elif re.search(r"\b(?:no[,.]?\s*i\s*(?:do\s*not|don'?t)\s*have\s*(?:a\s*)?farmer\s*id|no\s*farmer\s*(?:id|card))\b", lower):
                changes["farmer_id_status"] = "not_registered"
                explicitly_stated.append("farmer_id_status")

        # 14. Co-borrower / legal heir extraction
        if "co_borrower_legal_heir" not in changes:
            if re.search(r"\b(?:yes[,.]?\s*i\s*have\s*(?:a\s*)?co.?borrower|have\s*(?:a\s*)?co.?borrower|have\s*(?:a\s*)?legal\s*heir)\b", lower):
                changes["co_borrower_legal_heir"] = True
                explicitly_stated.append("co_borrower_legal_heir")
            elif re.search(r"\b(?:no[,.]?\s*i\s*(?:do\s*not|don'?t)\s*have\s*(?:a\s*)?co.?borrower|no\s*co.?borrower)\b", lower):
                changes["co_borrower_legal_heir"] = False
                explicitly_stated.append("co_borrower_legal_heir")

        # 15. Marital status extraction
        if "marriage_status" not in changes:
            if re.search(r"\b(?:married|i\s*am\s*married)\b", lower) and not re.search(r"\b(?:unmarried|un-married|not\s*married)\b", lower):
                changes["marriage_status"] = "married"
                explicitly_stated.append("marriage_status")
            elif re.search(r"\b(?:unmarried|un-married|not\s*married|single|bachelor|i\s*am\s*single)\b", lower):
                changes["marriage_status"] = "unmarried"
                explicitly_stated.append("marriage_status")
            elif re.search(r"\b(?:widow|widowed)\b", lower):
                changes["marriage_status"] = "widowed"
                explicitly_stated.append("marriage_status")
            elif re.search(r"\b(?:divorced|separated)\b", lower):
                changes["marriage_status"] = "divorced"
                explicitly_stated.append("marriage_status")

        # 16. Widow status extraction
        if "widow_status" not in changes:
            if re.search(r"\b(?:i\s*am\s*(?:a\s*)?widow|widow|widowed)\b", lower):
                changes["widow_status"] = True
                explicitly_stated.append("widow_status")

        # 17. Pregnancy/lactation status
        if "pregnancy_or_lactation_status" not in changes:
            if re.search(r"\b(?:pregnant|expecting|lactating|breastfeeding|nursing)\b", lower):
                changes["pregnancy_or_lactation_status"] = True
                explicitly_stated.append("pregnancy_or_lactation_status")

        # 18. Contextual resolution: If user is answering a direct question
        if last_asked_field and last_asked_field not in changes:
            if last_asked_field in ["annual_income_inr", "annual_family_income_inr"]:
                norm_val, is_ambig = normalize_income(text)
                if is_ambig:
                    ambiguous_fields.append(last_asked_field)
                elif norm_val is not None:
                    changes[last_asked_field] = norm_val
                    explicitly_stated.append(last_asked_field)
            elif last_asked_field in ["land_acres", "land_holding_acres"]:
                norm_val, is_ambig = normalize_land_acres(text)
                if is_ambig:
                    ambiguous_fields.append(last_asked_field)
                elif norm_val is not None:
                    changes[last_asked_field] = norm_val
                    explicitly_stated.append(last_asked_field)
            elif last_asked_field in ["age", "girl_child_age", "groom_age"]:
                # Guard: If asking citizen 'age' and user speaks about third-party, do not assign to citizen age
                if last_asked_field == "age" and has_third_person and not re.search(r"\b(?:i\s+am|i'm|my\s+age)\b", lower):
                    pass
                else:
                    norm_val, is_ambig = normalize_age(text)
                    if is_ambig:
                        ambiguous_fields.append(last_asked_field)
                    elif norm_val is not None:
                        changes[last_asked_field] = norm_val
                        explicitly_stated.append(last_asked_field)
            elif last_asked_field == "gender":
                # Direct short-answer gender fallback if asked directly
                if not has_third_person:
                    for g_key, g_val in GENDER_MAP.items():
                        if re.fullmatch(rf"\s*{re.escape(g_key)}[.,!]?\s*", lower):
                            changes["gender"] = g_val
                            explicitly_stated.append("gender")
                            break

        return ProfileExtractionResult(
            changes=changes,
            explicitly_stated_fields=explicitly_stated,
            ambiguous_fields=ambiguous_fields,
            unresolved_fields=unresolved_fields or [],
            needs_confirmation=len(changes) > 0,
        )

    def _post_process_and_normalize(
        self, result: ProfileExtractionResult
    ) -> ProfileExtractionResult:
        """
        Applies deterministic normalization to LLM extraction output and removes unsupported keys.
        """
        clean_changes: Dict[str, Any] = {}
        for field, raw_val in result.changes.items():
            if field not in SUPPORTED_PROFILE_FIELDS:
                logger.warning(f"Discarding unsupported field extracted by LLM: {field}")
                continue

            norm_val, is_ambiguous = normalize_field(field, raw_val)
            if is_ambiguous:
                if field not in result.ambiguous_fields:
                    result.ambiguous_fields.append(field)
            elif norm_val is not None:
                clean_changes[field] = norm_val

        result.changes = clean_changes
        return result
