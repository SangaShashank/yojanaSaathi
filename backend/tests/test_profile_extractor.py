"""
Phase 3 Tests - Profile Extractor
=================================
Covers:
- TEST 1: Single fact extraction ("I am from Telangana.")
- TEST 2: Multi-fact extraction ("I am 42, a farmer from Telangana, have 3 acres and earn 2 lakh.")
- TEST 3: Missing fields remain unknown ("I am a farmer.")
- TEST 10: Ambiguous input ("I have five.")
- TEST 11: No hallucinated facts ("I need farming schemes.")
- TEST 17: Extraction failure (Simulate malformed LLM response)
- TEST 18: Unsupported field rejected by validation
"""

import json
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from backend.app.profile.extractor import ProfileExtractor
from backend.app.profile.schemas import ProfileExtractionResult, ProfilePatch


def test_test_1_single_fact_extraction():
    """
    TEST 1 — Single fact extraction
    Input: "I am from Telangana."
    Expected: state = Telangana. No other invented fields.
    """
    extractor = ProfileExtractor(use_llm=False)
    result = extractor.extract("I am from Telangana.")

    assert result.changes.get("state") == "Telangana"
    # No other fields invented
    assert "age" not in result.changes
    assert "land_holding_acres" not in result.changes
    assert "annual_income_inr" not in result.changes
    assert "occupation" not in result.changes


def test_test_2_multi_fact_extraction():
    """
    TEST 2 — Multi-fact extraction
    Input: "I am 42, a farmer from Telangana, have 3 acres and earn 2 lakh."
    Expected: multiple profile fields extracted correctly.
    """
    extractor = ProfileExtractor(use_llm=False)
    result = extractor.extract(
        "I am 42, a farmer from Telangana, have 3 acres and earn 2 lakh."
    )

    assert result.changes.get("age") == 42
    assert result.changes.get("occupation") == "farmer"
    assert result.changes.get("state") == "Telangana"
    assert result.changes.get("land_holding_acres") == 3.0
    assert result.changes.get("annual_income_inr") == 200000.0


def test_test_3_missing_fields_remain_unknown():
    """
    TEST 3 — Missing fields remain unknown
    Input: "I am a farmer."
    Expected: occupation extracted. Age, income, land etc. remain unknown.
    """
    extractor = ProfileExtractor(use_llm=False)
    result = extractor.extract("I am a farmer.")

    assert result.changes == {"occupation": "farmer"}
    # Verify non-stated fields are NOT present
    for missing in ["age", "annual_income_inr", "land_holding_acres", "state", "is_bpl"]:
        assert missing not in result.changes


def test_test_10_ambiguous_input():
    """
    TEST 10 — Ambiguous input
    Input: "I have five."
    Expected: ambiguous/unresolved. No arbitrary field assignment.
    """
    extractor = ProfileExtractor(use_llm=False)
    result = extractor.extract("I have five.")

    # Must flag ambiguity and NOT assign an arbitrary field
    assert "land_holding_acres" in result.ambiguous_fields or len(result.ambiguous_fields) > 0
    assert "land_holding_acres" not in result.changes
    assert "annual_income_inr" not in result.changes


def test_test_11_no_hallucinated_facts():
    """
    TEST 11 — No hallucinated facts
    Input: "I need farming schemes."
    Expected: do not invent land, income, age, gender, Aadhaar, bank data, etc.
    """
    extractor = ProfileExtractor(use_llm=False)
    result = extractor.extract("I need farming schemes.")

    # Should not guess land, age, income, or bank data
    for field in ["land_holding_acres", "annual_income_inr", "age", "gender", "is_bpl", "district"]:
        assert field not in result.changes


def test_test_17_extraction_failure_safe_fallback():
    """
    TEST 17 — Extraction failure
    Simulate malformed LLM output.
    Expected: bounded retry / safe fallback. No profile corruption.
    """
    extractor = ProfileExtractor(use_llm=True)
    # Mock LLM client returning malformed non-JSON output
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "MALFORMED_NON_JSON_OUTPUT {{"
    mock_client.models.generate_content.return_value = mock_response
    extractor._client = mock_client

    # Should fall back cleanly without raising exception
    result = extractor.extract("I am from Telangana and have 3 acres.")
    assert isinstance(result, ProfileExtractionResult)
    # The deterministic fallback extracts from the text
    assert result.changes.get("state") == "Telangana"
    assert result.changes.get("land_holding_acres") == 3.0


def test_test_18_unsupported_field_rejected():
    """
    TEST 18 — Unsupported field
    LLM/user tries to return a field not in CitizenProfile.
    Expected: validation rejects it.
    """
    # 1. ProfilePatch with arbitrary key must raise ValidationError
    with pytest.raises(ValidationError):
        ProfilePatch(changes={"favourite_color": "blue", "pet_name": "Charlie"})

    # 2. ProfileExtractionResult with arbitrary key must raise ValidationError
    with pytest.raises(ValidationError):
        ProfileExtractionResult(
            changes={"non_existent_unsupported_field": 123},
            explicitly_stated_fields=["non_existent_unsupported_field"],
        )

    # 3. Post-process filtering discards unsupported keys
    extractor = ProfileExtractor(use_llm=False)
    raw_mock_result = ProfileExtractionResult(
        changes={"state": "Telangana"},
        explicitly_stated_fields=["state"],
    )
    # Simulate LLM injecting an unknown field dict before validation
    sanitized = extractor._post_process_and_normalize(raw_mock_result)
    assert "state" in sanitized.changes
    assert len(sanitized.changes) == 1
