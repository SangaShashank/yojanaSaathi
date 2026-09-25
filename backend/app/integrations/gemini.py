"""
Yojana Saathi - Gemini Integration Adapter
==========================================
Unified adapter interface for Gemini API operations (action proposing and profile fact extraction).
Never exposes API keys to client layers.
"""

from typing import Any, Dict, List, Optional
from backend.app.agent.actions import AgentAction
from backend.app.agent.provider import GeminiActionProvider
from backend.app.agent.state import AgentState
from backend.app.profile.extractor import ProfileExtractor
from backend.app.profile.schemas import ProfileExtractionResult


class GeminiIntegration:
    """Consolidated adapter wrapping Gemini-backed agent action and profile extraction subsystems."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.action_provider = GeminiActionProvider(api_key=api_key, model_name=model_name)
        self.profile_extractor = ProfileExtractor(api_key=api_key, model_name=model_name, use_llm=True)

    def propose_action(self, state: AgentState) -> AgentAction:
        """Proposes structured next AgentAction from current AgentState."""
        return self.action_provider.propose_action(state)

    def extract_profile_facts(
        self,
        text: str,
        current_profile: Optional[Dict[str, Any]] = None,
        unresolved_fields: Optional[List[str]] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> ProfileExtractionResult:
        """Extracts structured citizen profile facts from natural language text."""
        return self.profile_extractor.extract(
            text=text,
            current_profile=current_profile,
            unresolved_fields=unresolved_fields,
            conversation_context=conversation_context,
        )
