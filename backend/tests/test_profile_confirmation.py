"""
Phase 3 Tests - Human / CSC Confirmation and Eligibility Safety
===============================================================
Covers:
- TEST 6: Confirmation (Proposed land 3 -> 5, confirmed becomes 5)
- TEST 7: Rejection (Proposed land 3 -> 5, rejected remains 3)
- TEST 12: Confirmed-only eligibility (Pending proposal land=5; eligibility must see confirmed land=3)
- TEST 13: Eligibility after confirmation (Confirm land=5; eligibility now sees 5)
- TEST 14: Eligibility stale after profile change (Re-evaluating eligibility invalidated when relevant confirmed field changes)
"""

import pytest
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.controller import AgentController
from backend.app.agent.dispatcher import ActionDispatcher
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.agent.state import AgentState, StageEnum
from backend.app.agent.validator import ActionValidator
from backend.app.profile.coordinator import (
    confirm_pending_profile,
    process_user_message,
    reject_pending_profile,
)
from backend.app.schemas.profile import CitizenProfile
from backend.app.services.eligibility_engine import evaluate_all_schemes
from backend.app.services.scheme_loader import load_all_schemes


def test_test_6_confirmation_workflow():
    """
    TEST 6 — Confirmation
    Proposed change: land 3 -> 5
    Confirm.
    Expected: confirmed profile becomes 5.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        }
    )

    process_user_message(state, "Actually I have 5 acres.")
    assert state.pending_confirmation is not None
    assert state.profile["land_holding_acres"] == 3.0  # Not yet confirmed

    res = confirm_pending_profile(state)
    assert res["status"] == "CONFIRMED"
    assert state.profile["land_holding_acres"] == 5.0
    assert state.pending_confirmation is None


def test_test_7_rejection_workflow():
    """
    TEST 7 — Rejection
    Proposed change: land 3 -> 5
    Reject.
    Expected: confirmed profile remains 3.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        }
    )

    process_user_message(state, "Actually I have 5 acres.")
    assert state.pending_confirmation is not None

    res = reject_pending_profile(state)
    assert res["status"] == "REJECTED"
    # Confirmed profile strictly preserved at 3.0
    assert state.profile["land_holding_acres"] == 3.0
    assert state.pending_confirmation is None


def test_test_12_confirmed_only_eligibility():
    """
    TEST 12 — Confirmed-only eligibility
    Profile has: land = 3 confirmed.
    Pending proposal: land = 5.
    Before confirmation: eligibility must use land = 3.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
            "annual_income_inr": 150000.0,
        }
    )

    # Propose change to 5 acres
    process_user_message(state, "Actually I have 5 acres.")
    assert state.pending_confirmation is not None

    # The Phase 1 eligibility engine is called ONLY with confirmed profile:
    profile_for_engine = CitizenProfile.model_validate(state.profile)
    assert profile_for_engine.land_holding_acres == 3.0
    assert profile_for_engine.land_holding_acres != 5.0

    # Also, ActionValidator prevents RUN_ELIGIBILITY while pending_confirmation exists
    action = AgentAction(
        action=ActionType.RUN_ELIGIBILITY,
        reason_code=ReasonCode.ELIGIBILITY_READY,
    )
    is_valid, err = ActionValidator.validate(action, state)
    assert not is_valid
    assert "pending human confirmation" in err


def test_test_13_eligibility_after_confirmation():
    """
    TEST 13 — Eligibility after confirmation
    Confirm land = 5.
    Expected: eligibility sees land = 5.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
            "annual_income_inr": 150000.0,
        }
    )

    process_user_message(state, "Actually I have 5 acres.")
    confirm_pending_profile(state)

    profile_for_engine = CitizenProfile.model_validate(state.profile)
    assert profile_for_engine.land_holding_acres == 5.0


def test_test_14_eligibility_stale_after_profile_change():
    """
    TEST 14 — Eligibility stale after profile change
    Evaluate profile.
    Then change an eligibility-relevant field.
    Expected: previous eligibility result marked stale / invalid for current profile.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_ownership": True,
            "land_holding_acres": 3.0,
            "land_record_date": "2018-05-15",
            "farmer_id_status": "registered",
            "annual_income_inr": 150000.0,
        },
        candidate_schemes=["pm_kisan_001"],
    )

    # 1. Dispatch eligibility
    dispatcher = ActionDispatcher()
    action = AgentAction(
        action=ActionType.RUN_ELIGIBILITY,
        reason_code=ReasonCode.ELIGIBILITY_READY,
    )
    dispatcher.dispatch(action, state)

    assert state.stage == StageEnum.ELIGIBILITY_EVALUATED.value
    assert len(state.eligible_schemes) > 0 or len(state.eliminated_schemes) > 0
    assert state.evaluated_profile_fingerprint is not None

    # 2. User changes confirmed profile: income changes to 10 lakh (likely not eligible)
    process_user_message(state, "Actually my income is 10 lakh.")
    confirm_res = confirm_pending_profile(state)

    # Invalidation must have triggered
    assert confirm_res["eligibility_invalidated"] is True
    # Cached results must have been wiped
    assert len(state.eligible_schemes) == 0
    assert len(state.eliminated_schemes) == 0
    assert state.stage != StageEnum.ELIGIBILITY_EVALUATED.value
