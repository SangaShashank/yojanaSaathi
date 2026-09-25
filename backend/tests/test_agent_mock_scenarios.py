"""
Mandatory Test Cases & Agentic Proof Scenarios
==============================================
Implements:
- All 10 mandatory test cases from Section 20 of the prompt
- The multi-state Agentic Proof Trace from Section 21 of the prompt
"""

import pytest
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.controller import AgentController
from backend.app.agent.provider import DeterministicActionProvider, MockActionProvider
from backend.app.agent.state import AgentState, Contradiction, StageEnum, TerminationReason
from backend.app.agent.validator import ActionValidator


class TestMandatoryScenariosSection20:
    def test_01_missing_information(self):
        """TEST 1 — State: missing income -> Expected: ASK_QUESTION"""
        state = AgentState(
            profile={"age": 42, "state": "Telangana"},
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, _ = controller.step(state)

        assert activity.selected_action == ActionType.ASK_QUESTION.value
        assert activity.selected_field == "annual_income_inr"

    def test_02_complete_eligibility_profile(self):
        """TEST 2 — State: eligibility-critical information available -> Expected: RUN_ELIGIBILITY"""
        state = AgentState(
            profile={
                "age": 35,
                "state": "Telangana",
                "land_ownership": True,
                "land_record_date": "2018-05-10",
                "occupation": "farmer",
                "farmer_id_status": "registered",
            },
            missing_information=[],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, _ = controller.step(state)

        assert activity.selected_action == ActionType.RUN_ELIGIBILITY.value
        assert activity.reason_code == ReasonCode.ELIGIBILITY_READY.value

    def test_03_contradiction(self):
        """TEST 3 — State: contradictions != [] -> Expected: RESOLVE_CONTRADICTION"""
        state = AgentState(
            profile={"age": 42},
            missing_information=["annual_income_inr"],
            contradictions=[
                Contradiction(field="age", existing_value=42, conflicting_value=45)
            ],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, _ = controller.step(state)

        assert activity.selected_action == ActionType.RESOLVE_CONTRADICTION.value
        assert activity.selected_field == "age"

    def test_04_no_supported_schemes(self):
        """TEST 4 — State: evaluation complete + zero actionable configured schemes -> Expected: NO_SUPPORTED_MATCH"""
        state = AgentState(
            profile={"age": 42, "gender": "male", "occupation": "industrialist"},
            missing_information=[],
            candidate_schemes=[],
            eliminated_schemes=["pm_kisan_001", "sakhi_osc_001"],
            eligible_schemes=[],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, _ = controller.step(state)

        assert activity.selected_action == ActionType.NO_SUPPORTED_MATCH.value
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.NO_SUPPORTED_MATCH.value

    def test_05_already_complete(self):
        """TEST 5 — State: objective complete -> Expected: FINISH"""
        state = AgentState(
            stage="ELIGIBILITY_EVALUATED",
            eligible_schemes=["pm_kisan_001"],
            missing_information=[],
        )
        controller = AgentController(provider=DeterministicActionProvider())
        activity, _ = controller.step(state)

        assert activity.selected_action == ActionType.FINISH.value
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.OBJECTIVE_COMPLETE.value

    def test_06_human_verification(self):
        """TEST 6 — State: unsafe unresolved contradiction -> Expected: ESCALATE_HUMAN"""
        # When an unresolvable contradiction or explicit escalation is triggered
        action = AgentAction(
            action=ActionType.ESCALATE_HUMAN,
            reason_code=ReasonCode.HUMAN_VERIFICATION_REQUIRED,
            notes="Unresolvable identity mismatch requires official verification",
        )
        state = AgentState(contradictions=[Contradiction(field="aadhaar", existing_value="X", conflicting_value="Y")])
        mock_provider = MockActionProvider([action])
        controller = AgentController(provider=mock_provider)

        activity, _ = controller.step(state)
        assert activity.selected_action == ActionType.ESCALATE_HUMAN.value
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.HUMAN_VERIFICATION_REQUIRED.value

    def test_07_invalid_action(self):
        """
        TEST 7 — Force Gemini/mock provider to propose RUN_ELIGIBILITY when required information is missing.
        Expected: ActionValidator rejects it.
        """
        state = AgentState(
            profile={"age": 42},
            missing_information=["occupation", "farmer_id_status"],
            candidate_schemes=["pm_kisan_001"],
        )
        invalid_proposal = AgentAction(
            action=ActionType.RUN_ELIGIBILITY,
            tool="evaluate_eligibility",
            reason_code=ReasonCode.ELIGIBILITY_READY,
        )
        is_valid, err = ActionValidator.validate(invalid_proposal, state)

        assert is_valid is False
        assert "profile is incomplete" in err

    def test_08_repeated_question_protection(self):
        """
        TEST 8 — Simulate: ASK_QUESTION, profile unchanged, same question proposed again.
        Expected: Controller detects no progress and does not loop forever.
        """
        state = AgentState(
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        controller = AgentController(provider=DeterministicActionProvider())

        # Turn 1: Asks question
        controller.step(state)
        assert state.asked_questions == ["annual_income_inr"]

        # Turn 2: User did not answer, state unchanged.
        # Controller rejects repeating the question and terminates safely via fallback escalation
        controller.step(state)
        assert state.is_terminated is True
        assert state.termination_reason in [
            TerminationReason.HUMAN_VERIFICATION_REQUIRED.value,
            TerminationReason.NO_PROGRESS.value,
        ]

    def test_09_maximum_iterations(self):
        """
        TEST 9 — Force non-progressing actions.
        Expected: MAX_ITERATIONS terminal state.
        """
        state = AgentState(
            max_iterations=4,
            missing_information=["field_a", "field_b", "field_c", "field_d", "field_e"],
        )
        controller = AgentController(provider=DeterministicActionProvider())

        for _ in range(5):
            controller.step(state)

        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.MAX_ITERATIONS.value

    def test_10_state_dependent_action(self):
        """
        TEST 10 — Create two states with different conditions.
        Expected: Different next actions.
        PROVES GENUINE AGENTIC BEHAVIOR (state changes next action).
        """
        controller = AgentController(provider=DeterministicActionProvider())

        # State 1: Incomplete profile -> Must choose ASK_QUESTION
        state_1 = AgentState(
            profile={"age": 40},
            missing_information=["annual_income_inr"],
            candidate_schemes=["pm_kisan_001"],
        )
        act_1, _ = controller.step(state_1)

        # State 2: Complete profile -> Must choose RUN_ELIGIBILITY
        state_2 = AgentState(
            profile={
                "age": 40,
                "state": "Telangana",
                "land_ownership": True,
                "land_record_date": "2018-05-15",
                "occupation": "farmer",
                "farmer_id_status": "registered",
            },
            missing_information=[],
            candidate_schemes=["pm_kisan_001"],
        )
        act_2, _ = controller.step(state_2)

        # Confirm different actions selected purely due to differing states
        assert act_1.selected_action == ActionType.ASK_QUESTION.value
        assert act_2.selected_action == ActionType.RUN_ELIGIBILITY.value
        assert act_1.selected_action != act_2.selected_action


class TestAgenticProofScenarioSection21:
    def test_agentic_proof_trace(self):
        """
        SECTION 21 — AGENTIC PROOF TEST:
        Demonstrates state-driven evolution across multiple turns:
        STATE A: missing annual income -> Agent chooses ASK_QUESTION
        User answer updates state
        STATE B: profile now complete -> Agent chooses RUN_ELIGIBILITY
        Eligibility result changes the state
        STATE C: eligible stage -> Agent chooses FINISH
        """
        controller = AgentController(provider=DeterministicActionProvider())
        trace = []

        # ==========================================
        # TURN 1: STATE A (Incomplete Information)
        # ==========================================
        state = AgentState(
            case_id="CASE-PROOF-001",
            profile={
                "age": 35,
                "state": "Telangana",
                "land_ownership": True,
                "land_record_date": "2018-05-10",
                "occupation": "farmer",
            },
            missing_information=["farmer_id_status"],
            candidate_schemes=["pm_kisan_001"],
        )
        assert len(state.missing_information) == 1

        activity_1, _ = controller.step(state)
        trace.append({
            "turn": 1,
            "state_description": "profile_incomplete",
            "action": activity_1.selected_action,
            "field": activity_1.selected_field,
        })

        assert activity_1.selected_action == ActionType.ASK_QUESTION.value
        assert activity_1.selected_field == "farmer_id_status"

        # ==========================================
        # TURN 2: USER PROVIDES MISSING INFORMATION -> STATE B
        # ==========================================
        state.profile["farmer_id_status"] = "registered"
        state.missing_information.clear()  # Missing info resolved!
        state.stage = StageEnum.ELIGIBILITY_READY.value

        activity_2, _ = controller.step(state)
        trace.append({
            "turn": 2,
            "state_description": "profile_complete",
            "action": activity_2.selected_action,
            "field": activity_2.selected_field,
        })

        assert activity_2.selected_action == ActionType.RUN_ELIGIBILITY.value
        assert "pm_kisan_001" in state.eligible_schemes

        # ==========================================
        # TURN 3: STATE C (Eligibility Results Recorded)
        # ==========================================
        activity_3, _ = controller.step(state)
        trace.append({
            "turn": 3,
            "state_description": "eligibility_complete",
            "action": activity_3.selected_action,
            "field": activity_3.selected_field,
        })

        assert activity_3.selected_action == ActionType.FINISH.value
        assert state.is_terminated is True
        assert state.termination_reason == TerminationReason.OBJECTIVE_COMPLETE.value

        # Verify the sequential trace demonstrates non-linear, state-dependent decisions
        expected_actions = ["ASK_QUESTION", "RUN_ELIGIBILITY", "FINISH"]
        actual_actions = [step["action"] for step in trace]
        assert actual_actions == expected_actions

        print(f"\n[AGENTIC PROOF TRACE VERIFIED]: {trace}")
