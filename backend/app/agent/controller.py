"""
Yojana Saathi - Agent Controller
================================
Central Agent Controller running the real state-dependent loop:
OBSERVE -> IDENTIFY -> GENERATE -> PROPOSE -> VALIDATE -> DISPATCH -> UPDATE -> CHECK TERMINATION -> LOOP
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from backend.app.agent.actions import ActionType, AgentAction, AgentActivity, ReasonCode
from backend.app.agent.dispatcher import ActionDispatcher
from backend.app.agent.policies import DeterministicPolicy, generate_valid_actions
from backend.app.agent.provider import ActionProvider, DeterministicActionProvider, GeminiActionProvider
from backend.app.agent.state import AgentState, StageEnum, TerminationReason
from backend.app.agent.validator import ActionValidator

logger = logging.getLogger(__name__)


class AgentController:
    """
    Yojana Saathi Agent Controller.
    Dynamically decides next valid actions from AgentState with zero hardcoded questionnaire sequences.
    """

    def __init__(
        self,
        provider: Optional[ActionProvider] = None,
        dispatcher: Optional[ActionDispatcher] = None,
    ):
        self.provider = provider or GeminiActionProvider()
        self.dispatcher = dispatcher or ActionDispatcher()

    def step(self, state: AgentState) -> Tuple[AgentActivity, Dict[str, Any]]:
        """
        Executes a single iteration of the Agentic loop.
        """
        if state.is_terminated:
            activity = AgentActivity(
                iteration=state.iteration,
                stage=state.stage,
                missing_information=list(state.missing_information),
                candidate_schemes_count=len(state.candidate_schemes),
                available_actions=[ActionType.FINISH.value],
                selected_action=ActionType.FINISH.value,
                reason_code=ReasonCode.TERMINAL_STATE.value,
                state_fingerprint=state.get_fingerprint(),
                termination_reason=state.termination_reason,
            )
            return activity, {"status": "ALREADY_TERMINATED"}

        # 1. Loop Boundedness Check
        state.iteration += 1
        if state.iteration > state.max_iterations:
            state.mark_terminated(TerminationReason.MAX_ITERATIONS)
            activity = AgentActivity(
                iteration=state.iteration,
                stage=state.stage,
                missing_information=list(state.missing_information),
                candidate_schemes_count=len(state.candidate_schemes),
                available_actions=[],
                selected_action=ActionType.FINISH.value,
                reason_code=ReasonCode.MAX_ITERATIONS_REACHED.value,
                state_fingerprint=state.get_fingerprint(),
                termination_reason=TerminationReason.MAX_ITERATIONS.value,
            )
            return activity, {"status": "TERMINATED_MAX_ITERATIONS"}

        fingerprint_before = state.get_fingerprint()

        # 2. Observe State & Generate Available Valid Actions
        available_actions = generate_valid_actions(state)
        available_action_names = [a.action.value for a in available_actions]

        # 3. Propose Next Action via Provider (Gemini or Deterministic Policy)
        proposed_action = self.provider.propose_action(state)

        # 4. Action Validation Gate
        is_valid, validation_error = ActionValidator.validate(proposed_action, state)
        action_to_execute = proposed_action

        if not is_valid:
            logger.warning(
                f"[Iteration {state.iteration}] Proposed action '{proposed_action.action}' rejected: {validation_error}. Triggering fallback."
            )
            # Safe Fallback: select top-ranked valid action from deterministic policy
            fallback_action = DeterministicPolicy.select_action(state)
            fallback_is_valid, _ = ActionValidator.validate(fallback_action, state)

            if fallback_is_valid:
                action_to_execute = fallback_action
                action_to_execute.reason_code = ReasonCode.INVALID_ACTION_FALLBACK
            else:
                action_to_execute = AgentAction(
                    action=ActionType.ESCALATE_HUMAN,
                    reason_code=ReasonCode.INVALID_ACTION_FALLBACK,
                    notes=f"Fallback escalation due to validation rejection: {validation_error}",
                )

        # 5. Execute Action via Controlled Dispatcher
        success, exec_result, dispatch_error = self.dispatcher.dispatch(action_to_execute, state)
        if not success:
            logger.error(f"Dispatch failed for {action_to_execute.action}: {dispatch_error}")
            state.mark_terminated(TerminationReason.HUMAN_VERIFICATION_REQUIRED)

        fingerprint_after = state.get_fingerprint()

        # 6. Lack-of-Progress & Stale-State Protection
        if fingerprint_before == fingerprint_after:
            state.consecutive_unchanged_iterations += 1
            if state.consecutive_unchanged_iterations >= 2:
                logger.warning(
                    f"No progress detected after {state.consecutive_unchanged_iterations} consecutive iterations. Halting loop to prevent cycle."
                )
                state.mark_terminated(TerminationReason.NO_PROGRESS)
        else:
            state.consecutive_unchanged_iterations = 0

        # Update loop tracking
        state.last_action = action_to_execute
        state.last_state_fingerprint = fingerprint_after

        # 7. Build Observability Activity Object
        activity = AgentActivity(
            iteration=state.iteration,
            stage=state.stage,
            missing_information=list(state.missing_information),
            candidate_schemes_count=len(state.candidate_schemes),
            available_actions=available_action_names,
            selected_action=action_to_execute.action.value,
            selected_field=action_to_execute.field,
            reason_code=action_to_execute.reason_code.value,
            tool_called=action_to_execute.tool,
            state_fingerprint=fingerprint_after,
            termination_reason=state.termination_reason,
        )

        return activity, exec_result

    def run_until_pause_or_completion(
        self, state: AgentState, max_steps: Optional[int] = None
    ) -> List[AgentActivity]:
        """
        Runs the agentic loop iteratively until it reaches:
        1. A terminal state (OBJECTIVE_COMPLETE, NO_SUPPORTED_MATCH, etc.), or
        2. WAITING_FOR_USER_INPUT (Agent asks a question and pauses for the citizen's response), or
        3. Optional max_steps budget.
        """
        activities: List[AgentActivity] = []
        steps_taken = 0
        limit = max_steps or state.max_iterations

        while not state.is_terminated and steps_taken < limit:
            activity, result = self.step(state)
            activities.append(activity)
            steps_taken += 1

            # Pause loop if Agent has asked a question and is awaiting user response
            if state.stage == StageEnum.WAITING_FOR_USER_INPUT.value:
                break

        return activities
