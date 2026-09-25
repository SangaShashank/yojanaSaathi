"""
Unit Tests for ActionValidator
==============================
Validates that invalid LLM proposals are rejected and valid actions are accepted.
"""

import pytest
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.state import AgentState, Contradiction
from backend.app.agent.validator import ActionValidator


class TestActionValidator:
    def test_validate_ask_question_valid(self):
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        action = AgentAction(
            action=ActionType.ASK_QUESTION,
            field="annual_income_inr",
            question="What is your annual income?",
            reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is True
        assert err is None

    def test_validate_ask_question_missing_target_field(self):
        state = AgentState(missing_information=["age"])
        action = AgentAction(
            action=ActionType.ASK_QUESTION,
            field=None,  # Missing target field
            question="What is your age?",
            reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "requires a target 'field'" in err

    def test_validate_ask_question_field_already_confirmed(self):
        """Cannot ask for a field that is already confirmed and known."""
        state = AgentState(
            profile={"age": 42},
            missing_information=["annual_income_inr"],
        )
        action = AgentAction(
            action=ActionType.ASK_QUESTION,
            field="age",  # Already known!
            question="What is your age?",
            reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "already known and confirmed" in err

    def test_validate_ask_question_field_not_in_missing_info(self):
        state = AgentState(missing_information=["annual_income_inr"])
        action = AgentAction(
            action=ActionType.ASK_QUESTION,
            field="favorite_color",  # Irrelevant field
            question="What is your favorite color?",
            reason_code=ReasonCode.MAX_EXPECTED_NARROWING,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "not in current missing_information" in err

    def test_validate_run_eligibility_valid(self):
        state = AgentState(
            profile={"age": 42, "state": "Telangana", "land_ownership": True},
            missing_information=[],  # Complete!
            candidate_schemes=["pm_kisan_001"],
            contradictions=[],
        )
        action = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is True
        assert err is None

    def test_validate_run_eligibility_fails_when_missing_info_remains(self):
        state = AgentState(
            profile={"age": 42},
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        action = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "profile is incomplete" in err

    def test_validate_run_eligibility_fails_when_contradictions_exist(self):
        state = AgentState(
            profile={"age": 42},
            missing_information=[],
            candidate_schemes=["pm_kisan_001"],
            contradictions=[Contradiction(field="age", existing_value=42, conflicting_value=45)],
        )
        action = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "unresolved contradiction" in err

    def test_validate_resolve_contradiction(self):
        # Case A: Contradiction exists -> valid
        state_with_conflict = AgentState(
            contradictions=[Contradiction(field="land_acres", existing_value=3, conflicting_value=5)]
        )
        action = AgentAction(
            action=ActionType.RESOLVE_CONTRADICTION,
            field="land_acres",
            question="Which land size is correct?",
            reason_code=ReasonCode.RESOLVE_CONTRADICTION,
        )
        assert ActionValidator.validate(action, state_with_conflict)[0] is True

        # Case B: No contradictions -> invalid
        state_clean = AgentState(contradictions=[])
        assert ActionValidator.validate(action, state_clean)[0] is False

    def test_validate_no_supported_match_fails_when_eligible_exist(self):
        state = AgentState(eligible_schemes=["pm_kisan_001"])
        action = AgentAction(
            action=ActionType.NO_SUPPORTED_MATCH,
            reason_code=ReasonCode.NO_SUPPORTED_MATCH,
        )
        is_valid, err = ActionValidator.validate(action, state)
        assert is_valid is False
        assert "Cannot declare NO_SUPPORTED_MATCH" in err
