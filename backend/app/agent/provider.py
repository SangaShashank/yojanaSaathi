"""
Yojana Saathi - Action Provider (Gemini & Deterministic/Mock)
============================================================
Handles LLM structured action proposals with graceful fallback.
Server-side only; API keys are never exposed to clients.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional
from backend.app.agent.actions import ActionType, AgentAction, ReasonCode
from backend.app.agent.policies import DeterministicPolicy
from backend.app.agent.prompts import AGENT_CONTROLLER_SYSTEM_PROMPT, format_state_for_prompt
from backend.app.agent.state import AgentState

logger = logging.getLogger(__name__)


class ActionProvider:
    """Base interface for action proposal providers."""

    def propose_action(self, state: AgentState) -> AgentAction:
        raise NotImplementedError


class DeterministicActionProvider(ActionProvider):
    """Pure deterministic rule-based provider for offline testing and guaranteed fallback."""

    def propose_action(self, state: AgentState) -> AgentAction:
        return DeterministicPolicy.select_action(state)


class MockActionProvider(ActionProvider):
    """
    Test provider that can return programmed actions or simulate malformed / invalid LLM outputs.
    """

    def __init__(self, actions: Optional[List[AgentAction]] = None):
        self._actions: List[AgentAction] = actions or []
        self._index = 0
        self.call_count = 0

    def add_action(self, action: AgentAction) -> None:
        self._actions.append(action)

    def propose_action(self, state: AgentState) -> AgentAction:
        self.call_count += 1
        if self._index < len(self._actions):
            act = self._actions[self._index]
            self._index += 1
            return act
        # Fallback to deterministic policy if scripted actions exhausted
        return DeterministicPolicy.select_action(state)


class GeminiActionProvider(ActionProvider):
    """
    Gemini-powered action proposal engine using google.genai client.
    Enforces structured Pydantic output and falls back cleanly on error.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_policy: Optional[ActionProvider] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.fallback = fallback_policy or DeterministicActionProvider()
        self._client = None

        if self.api_key:
            try:
                import google.genai as genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}. Using deterministic fallback.")

    def propose_action(self, state: AgentState) -> AgentAction:
        if not self._client or not self.api_key:
            return self.fallback.propose_action(state)

        prompt_text = format_state_for_prompt({
            "goal": state.goal,
            "profile": state.profile,
            "candidate_schemes": state.candidate_schemes,
            "missing_information": state.missing_information,
            "asked_questions": state.asked_questions,
            "contradictions": [c.model_dump() for c in state.contradictions if not c.resolved],
            "stage": state.stage,
            "iteration": state.iteration,
        })

        # Bounded retry loop (max 2 attempts)
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt_text,
                    config={
                        "system_instruction": AGENT_CONTROLLER_SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_schema": AgentAction,
                        "temperature": 0.0,
                    },
                )
                if response and response.text:
                    parsed_dict = json.loads(response.text)
                    return AgentAction.model_validate(parsed_dict)
            except Exception as e:
                logger.warning(f"Gemini generation attempt {attempt + 1} failed: {e}")

        # Fallback on failure
        logger.info("Falling back to deterministic policy after Gemini failure.")
        fallback_act = self.fallback.propose_action(state)
        fallback_act.reason_code = ReasonCode.INVALID_ACTION_FALLBACK
        return fallback_act
