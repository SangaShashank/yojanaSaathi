"""
Unit Tests for AgentController
==============================
Tests step execution, tool dispatch, and integration with Phase 1 deterministic engine.
"""

import pytest
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider, MockActionProvider
from backend.app.agent.state import AgentState, StageEnum, TerminationReason


class TestAgentController:
    def test_controller_step_asks_question_when_info_missing(self):
        state = AgentState(
            profile={"age": 42, "state": "Telangana"},
            missing_information=["occupation"],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, result = controller.step(state)

        assert activity.selected_action == ActionType.ASK_QUESTION.value
        assert activity.selected_field == "occupation"
        assert state.stage == StageEnum.WAITING_FOR_USER_INPUT.value
        assert "occupation" in state.asked_questions
        assert state.iteration == 1

    def test_controller_step_invokes_phase_1_eligibility(self):
        """
        Confirms AgentController invokes the Phase 1 deterministic eligibility engine
        and updates state.eligible_schemes.
        """
        state = AgentState(
            profile={
                "age": 35,
                "state": "Telangana",
                "land_ownership": True,
                "land_record_date": "2018-05-10",
                "occupation": "farmer",
                "farmer_id_status": "registered",
            },
            missing_information=[],  # Complete profile
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, result = controller.step(state)

        assert activity.selected_action == ActionType.RUN_ELIGIBILITY.value
        assert state.stage == StageEnum.ELIGIBILITY_EVALUATED.value
        assert "pm_kisan_001" in state.eligible_schemes
        assert result["action_executed"] == ActionType.RUN_ELIGIBILITY.value

    def test_controller_pauses_on_waiting_user_input(self):
        """
        run_until_pause_or_completion must stop when a question is asked
        so external user input can be provided.
        """
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activities = controller.run_until_pause_or_completion(state)

        assert len(activities) == 1
        assert activities[0].selected_action == ActionType.ASK_QUESTION.value
        assert state.stage == StageEnum.WAITING_FOR_USER_INPUT.value
        assert not state.is_terminated

    def test_controller_rejection_triggers_safe_fallback(self):
        """
        When a provider proposes an invalid action (e.g. RUN_ELIGIBILITY on incomplete state),
        the controller rejects it, logs the violation, and executes a valid fallback.
        """
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        # Mock provider forces an invalid RUN_ELIGIBILITY action
        invalid_action = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
        )
        mock_provider = MockActionProvider([invalid_action])
        controller = AgentController(provider=mock_provider)

        activity, result = controller.step(state)

        # Proposed action was rejected -> fallback executed ASK_QUESTION
        assert activity.selected_action == ActionType.ASK_QUESTION.value
        assert activity.reason_code == ReasonCode.INVALID_ACTION_FALLBACK.value
        assert state.stage == StageEnum.WAITING_FOR_USER_INPUT.value
