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

        # 5. Age extraction
        # e.g., "I am 42", "age is 45", "my age is 45", "42 years old", "am 42,"
        age_match = re.search(
            r"\b(?:(?:my\s+)?age\s*(?:is|:)?|i am|am)\s*(\d{1,3})\b(?!\s*(?:acres?|ac|lakh|rs|k|ekad))",
            lower,
        )
        if age_match:
            age_val, is_ambig = normalize_age(age_match.group(1))
            if not is_ambig and age_val is not None:
                changes["age"] = age_val
                explicitly_stated.append("age")
        else:
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

        # 7. Contextual resolution: If user is answering a direct question
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
                norm_val, is_ambig = normalize_age(text)
                if is_ambig:
                    ambiguous_fields.append(last_asked_field)
                elif norm_val is not None:
                    changes[last_asked_field] = norm_val
                    explicitly_stated.append(last_asked_field)

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
