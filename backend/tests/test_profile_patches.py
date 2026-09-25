"""
Phase 3 Tests - Profile Patches and Contradictions
==================================================
Covers:
- TEST 4: Field-level patch (Existing: land = 3. Input: "Actually I have 5 acres." -> patch only land)
- TEST 5: Manual edit path (Directly patch annual_income_inr = 150000 -> same confirmation mechanism)
- TEST 8: Correction after confirmation (Confirmed income 200000 -> new input 150000 -> confirmed 150000)
- TEST 9: Contradiction (Confirmed age = 42 -> Input: "My age is 45." -> contradiction flagged, no auto overwrite)
- TEST 19: Partial update preservation (Existing: age, state, occ, land. Patch income -> existing preserved)
- TEST 20: State fingerprint change (Confirmed profile changes -> AgentState fingerprint changes)
"""

import pytest
from backend.app.agent.state import AgentState
from backend.app.profile.confirmation import ConfirmationManager
from backend.app.profile.coordinator import (
    apply_manual_edit,
    confirm_pending_profile,
    process_user_message,
)
from backend.app.profile.patcher import ProfilePatcher
from backend.app.profile.schemas import ConfirmationStatus, ProfilePatch


def test_test_4_field_level_patch():
    """
    TEST 4 — Field-level patch
    Existing: land = 3
    Input: "Actually I have 5 acres."
    Expected: patch only land_holding_acres = 5. No unrelated fields changed.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        }
    )

    patch = ProfilePatcher.create_patch({"land_holding_acres": 5.0})
    assert patch.changes == {"land_holding_acres": 5.0}

    # Generate changes
    change_items = ProfilePatcher.generate_change_items(state.profile, patch)
    assert len(change_items) == 1
    assert change_items[0].field == "land_holding_acres"
    assert change_items[0].previous == 3.0
    assert change_items[0].proposed == 5.0

    # Apply patch
    updated = ProfilePatcher.apply_patch(state.profile, patch)
    assert updated["land_holding_acres"] == 5.0
    assert updated["age"] == 42
    assert updated["state"] == "Telangana"
    assert updated["occupation"] == "farmer"


def test_test_5_manual_edit_path():
    """
    TEST 5 — Manual edit path
    Directly patch: annual_income_inr = 150000.
    Expected: same confirmation mechanism as natural-language correction.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        }
    )

    # 1. Manual edit staging for confirmation
    res = apply_manual_edit(state, "annual_income_inr", 150000)
    assert res["status"] == "CONFIRMATION_REQUIRED"
    assert state.pending_confirmation is not None

    # Verify confirmation items
    assert len(res["changes"]) == 1
    assert res["changes"][0]["field"] == "annual_income_inr"
    assert res["changes"][0]["proposed"] == 150000.0

    # 2. Confirm manual edit
    confirm_res = confirm_pending_profile(state)
    assert confirm_res["status"] == "CONFIRMED"
    assert state.profile["annual_income_inr"] == 150000.0
    # Unrelated fields remain intact
    assert state.profile["age"] == 42
    assert state.profile["land_holding_acres"] == 3.0


def test_test_8_correction_after_confirmation():
    """
    TEST 8 — Correction after confirmation
    Confirmed: income = 200000.
    New input: "My actual income is 150000."
    Expected: new pending patch. After confirmation: income = 150000.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "annual_income_inr": 200000.0,
        }
    )

    # User issues a natural-language correction
    res = process_user_message(state, "My actual income is 150000.")
    assert res["status"] == "CONFIRMATION_REQUIRED"
    assert state.pending_confirmation is not None
    assert res["changes"][0]["previous"] == 200000.0
    assert res["changes"][0]["proposed"] == 150000.0

    # Before confirmation, profile still holds old confirmed value
    assert state.profile["annual_income_inr"] == 200000.0

    # User confirms correction
    confirm_res = confirm_pending_profile(state)
    assert confirm_res["status"] == "CONFIRMED"
    assert state.profile["annual_income_inr"] == 150000.0
    assert state.profile["age"] == 42


def test_test_9_contradiction_detection():
    """
    TEST 9 — Contradiction
    Confirmed: age = 42.
    Input: "My age is 45."
    Expected: proposed change / contradiction requiring confirmation.
    No automatic replacement.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
        }
    )

    res = process_user_message(state, "My age is 45.")
    assert res["status"] == "CONFIRMATION_REQUIRED"

    # Confirmed profile must not be automatically overwritten
    assert state.profile["age"] == 42

    # Contradiction recorded in state
    assert len(state.contradictions) == 1
    assert state.contradictions[0].field == "age"
    assert state.contradictions[0].existing_value == 42
    assert state.contradictions[0].conflicting_value == 45


def test_test_19_partial_update_preservation():
    """
    TEST 19 — Partial update preservation
    Existing profile has: age, state, occupation, land.
    Patch only income.
    Expected: all existing fields preserved.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        }
    )

    patch = ProfilePatcher.create_patch({"annual_income_inr": 200000.0})
    updated = ProfilePatcher.apply_patch(state.profile, patch)

    assert updated["annual_income_inr"] == 200000.0
    assert updated["age"] == 42
    assert updated["state"] == "Telangana"
    assert updated["occupation"] == "farmer"
    assert updated["land_holding_acres"] == 3.0


def test_test_20_state_fingerprint_change():
    """
    TEST 20 — State fingerprint change
    Confirmed profile changes.
    Expected: AgentState fingerprint changes.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
        }
    )
    fp1 = state.get_fingerprint()

    # Apply manual edit
    apply_manual_edit(state, "land_holding_acres", 5.0, auto_confirm=True)
    fp2 = state.get_fingerprint()

    assert fp1 != fp2
