"""
Unit Tests for Agent Loop Protections and Termination
=====================================================
Tests loop safety: max iterations, no-progress detection, and repeated question guards.
"""

import pytest
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider, MockActionProvider
from backend.app.agent.state import AgentState, TerminationReason


class TestAgentLoopSafety:
    def test_max_iterations_protection(self):
        """Loop must terminate when iteration count exceeds max_iterations."""
        state = AgentState(
            max_iterations=3,
            missing_information=["field_1", "field_2", "field_3", "field_4"],
        )
        controller = AgentController(provider=DeterministicActionProvider())

        # Step 1, 2, 3
        controller.step(state)
        controller.step(state)
        controller.step(state)
        assert not state.is_terminated

        # Step 4 (exceeds max_iterations=3)
        activity, result = controller.step(state)
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.MAX_ITERATIONS.value
        assert activity.termination_reason == TerminationReason.MAX_ITERATIONS.value

    def test_no_progress_stale_state_protection(self):
        """
        If consecutive iterations produce no state change, the controller
        must detect lack of progress and terminate safely rather than looping infinitely.
        """
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        # Force a provider that repeatedly proposes clarification without state update
        static_action = AgentAction(
            action=ActionType.REQUEST_CLARIFICATION,
            question="Please clarify your situation.",
            reason_code=ReasonCode.NO_ACTIONABLE_INFORMATION,
        )
        mock_provider = MockActionProvider([static_action, static_action, static_action])
        controller = AgentController(provider=mock_provider)

        # Iteration 1
        controller.step(state)
        assert state.consecutive_unchanged_iterations == 0  # First run sets baseline

        # Iteration 2 (fingerprint unchanged)
        controller.step(state)
        assert state.consecutive_unchanged_iterations == 1

        # Iteration 3 (still unchanged -> triggers NO_PROGRESS termination)
        controller.step(state)
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.NO_PROGRESS.value

    def test_repeated_question_protection(self):
        """
        The Agent must not ask the exact same question repeatedly if the user has not answered.
        """
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())

        # Step 1: asks for annual_income_inr
        controller.step(state)
        assert state.asked_questions == ["annual_income_inr"]

        # Step 2 without user answer: state is unchanged.
        # If provider tries to ask annual_income_inr again, ActionValidator rejects it.
        invalid_repeat = AgentAction(
            action=ActionType.ASK_QUESTION,
            field="annual_income_inr",
            question="What is your annual income?",
            reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
        )
        from backend.app.agent.validator import ActionValidator
        is_valid, err = ActionValidator.validate(invalid_repeat, state)
        assert is_valid is False
        assert "Repeated question guard" in err
