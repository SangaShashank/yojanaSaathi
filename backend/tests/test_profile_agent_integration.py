"""
Phase 3 Tests - Agent Controller Integration
============================================
Covers:
- TEST 15: Multi-turn controller integration (Input -> extraction -> confirmation -> Agent resumes & picks next action)
- TEST 16: User answers Agent question (Agent asks income -> user replies -> extraction -> confirmation -> state updated)
- Section 33: End-to-End Agentic Integration Test (Full cycle: User input -> Profile update -> State change -> Agent decision -> Eligibility execution)
"""

import pytest
from backend.app.agent.actions import ActionType
from backend.app.agent.controller import AgentController
from backend.app.agent.dispatcher import ActionDispatcher
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.agent.state import AgentState, StageEnum
from backend.app.profile.coordinator import (
    confirm_pending_profile,
    process_user_message,
)
from backend.app.services.scheme_loader import load_all_schemes


def test_test_15_multi_turn_controller_integration():
    """
    TEST 15 — Multi-turn controller integration
    Turn 1: "I am a farmer from Telangana and have 3 acres."
    -> extraction -> proposed changes -> confirmation
    Turn 2: confirm
    -> confirmed profile -> Agent observes state -> determines remaining missing fields -> chooses next action
    """
    state = AgentState(candidate_schemes=["pm_kisan_001", "ts_rythu_bharosa_001"])
    controller = AgentController(provider=DeterministicActionProvider())

    # Turn 1: User provides multiple facts
    res = process_user_message(state, "I am a farmer from Telangana and have 3 acres.")
    assert res["status"] == "CONFIRMATION_REQUIRED"
    assert state.stage == StageEnum.WAITING_FOR_PROFILE_CONFIRMATION.value

    # Turn 2: Confirm
    confirm_res = confirm_pending_profile(state)
    assert confirm_res["status"] == "CONFIRMED"
    assert state.profile["state"] == "Telangana"
    assert state.profile["occupation"] == "farmer"
    assert state.profile["land_holding_acres"] == 3.0

    # Agent Controller now steps
    activity, exec_result = controller.step(state)

    # Agent observes updated profile facts and determines next action
    assert activity.selected_action in [ActionType.ASK_QUESTION.value, ActionType.RUN_ELIGIBILITY.value]
    if activity.selected_action == ActionType.ASK_QUESTION.value:
        # It must NOT ask for state, occupation, or land since they are confirmed!
        assert activity.selected_field not in ["state", "occupation", "land_holding_acres"]


def test_test_16_user_answers_agent_question():
    """
    TEST 16 — User answers Agent question
    Agent asks: "What is your approximate annual family income in rupees?"
    User replies: "My annual family income is 1.8 lakh."
    Expected: extract income -> proposed patch -> confirmation -> confirmed profile -> Agent resumes.
    """
    state = AgentState(
        profile={
            "age": 42,
            "state": "Telangana",
            "occupation": "farmer",
            "land_holding_acres": 3.0,
        },
        candidate_schemes=["PM-KISAN"],
    )
    # Simulate agent asking question
    state.add_asked_question("annual_income_inr", "What is your approximate annual family income in rupees?")
    state.stage = StageEnum.WAITING_FOR_USER_INPUT.value

    # User answers
    res = process_user_message(state, "My annual family income is 1.8 lakh.")
    assert res["status"] == "CONFIRMATION_REQUIRED"
    assert res["changes"][0]["field"] == "annual_income_inr"
    assert res["changes"][0]["proposed"] == 180000.0

    # Confirmation
    confirm_res = confirm_pending_profile(state)
    assert confirm_res["status"] == "CONFIRMED"
    assert state.profile["annual_income_inr"] == 180000.0


def test_section_33_end_to_end_agentic_integration():
    """
    Section 33 — End-to-End Agentic Integration Test
    Proves Phase 3 connects correctly to Phase 2:
    USER INPUT -> PROFILE UPDATE -> STATE CHANGE -> AGENT DECISION -> PHASE 1 ELIGIBILITY
    """
    state = AgentState(
        goal="Determine welfare schemes for farmer",
        candidate_schemes=["pm_kisan_001", "ts_rythu_bharosa_001"],
    )
    controller = AgentController(provider=DeterministicActionProvider())

    # 1. Initial message from citizen
    step1 = process_user_message(state, "I am a farmer from Telangana and I have 3 acres.")
    assert step1["status"] == "CONFIRMATION_REQUIRED"
    assert state.pending_confirmation is not None

    # 2. System asks for confirmation, citizen confirms
    confirm1 = confirm_pending_profile(state)
    assert confirm1["status"] == "CONFIRMED"
    assert state.profile["occupation"] == "farmer"
    assert state.profile["state"] == "Telangana"
    assert state.profile["land_holding_acres"] == 3.0

    # 3. Agent Controller observes current state and decides next action
    act1, res1 = controller.step(state)

    # 4. If critical fields remain missing (e.g. land_record_date or annual_income_inr), Agent asks a question
    if act1.selected_action == ActionType.ASK_QUESTION.value:
        asked_field = act1.selected_field
        assert asked_field in state.missing_information

        # 5. User provides the requested answer
        if asked_field == "land_record_date":
            step2 = process_user_message(state, "My land record was registered on 2018-05-15.")
            # If date was not parsed directly by regex, provide manual edit
            if not step2.get("changes"):
                from backend.app.profile.coordinator import apply_manual_edit
                apply_manual_edit(state, "land_record_date", "2018-05-15")
        elif asked_field in ["annual_income_inr", "annual_family_income_inr"]:
            step2 = process_user_message(state, "My annual income is 1.5 lakh.")
        elif asked_field == "age":
            step2 = process_user_message(state, "I am 42 years old.")
        else:
            from backend.app.profile.coordinator import apply_manual_edit
            apply_manual_edit(state, asked_field, True)

        confirm_pending_profile(state)

    # 6. Ensure any remaining required fields for PM-KISAN / TS-RYTHU-BHAROSA are fulfilled
    state.profile["land_record_date"] = "2018-05-15"
    state.profile["annual_income_inr"] = 150000.0
    state.profile["age"] = 42
    state.profile["farmer_id_status"] = "active"
    state.profile["active_cultivation_status"] = True
    state.profile["land_ownership"] = True
    state.profile["land_verification_source"] = "bhu_bharati"
    state.profile["occupation_type"] = "landowner"
    state.recompute_missing_information()

    # 7. Agent Controller steps now that profile is complete
    act_elig, res_elig = controller.step(state)

    # 8. Agent selects RUN_ELIGIBILITY
    assert act_elig.selected_action == ActionType.RUN_ELIGIBILITY.value

    # 9. Phase 1 deterministic engine has executed!
    assert state.stage == StageEnum.ELIGIBILITY_EVALUATED.value
    assert len(state.eligible_schemes) > 0 or len(state.eliminated_schemes) > 0
    assert state.evaluated_profile_fingerprint == state.get_profile_fingerprint()

    # 10. Final step: Agent controller finishes
    act_finish, res_finish = controller.step(state)
    assert act_finish.selected_action == ActionType.FINISH.value
    assert state.is_terminated is True
