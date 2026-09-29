"""
Yojana Saathi - Voice & Audio Schemas
=====================================
API request and response schemas for Phase 8 Multilingual Voice & Audio.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_LANGUAGES = ["en", "hi", "te"]

LANGUAGE_METADATA = {
    "en": {
        "code": "en",
        "name": "English",
        "locales": ["en-IN", "en-US", "en-GB", "en"],
        "default_locale": "en-IN",
    },
    "hi": {
        "code": "hi",
        "name": "हिन्दी (Hindi)",
        "locales": ["hi-IN", "hi"],
        "default_locale": "hi-IN",
    },
    "te": {
        "code": "te",
        "name": "తెలుగు (Telugu)",
        "locales": ["te-IN", "te"],
        "default_locale": "te-IN",
    },
}


class VoiceTurnResponse(BaseModel):
    """
    Structured response returned from the voice turn endpoint.
    Feeds the client-side browser SpeechSynthesis for TTS playback.
    """
    model_config = ConfigDict(extra="allow")

    turn_id: str = Field(description="Unique idempotency ID for this voice turn")
    case_id: str = Field(description="Case identifier")
    input_mode: str = Field(default="VOICE", description="Modality of interaction: VOICE or TYPED")
    language: str = Field(default="en", description="Selected interaction language: en, hi, or te")
    detected_language: Optional[str] = Field(default=None, description="STT-detected speech language")
    transcript: str = Field(default="", description="Transcribed speech text (untrusted user input)")
    response_text: str = Field(description="Concise, speakable text response for TTS / display")
    response_language: str = Field(default="en", description="Target language of response text")
    agent_action: Optional[str] = Field(default=None, description="Current or proposed agent action")
    state_updated: bool = Field(default=False, description="Whether case / profile state was modified")
    tts_available: bool = Field(default=True, description="Whether browser TTS can be invoked")
    tts_locales: List[str] = Field(default_factory=list, description="Target browser voice locales for TTS")
    status: str = Field(default="SUCCESS", description="Turn status: SUCCESS, CONFIRMATION_REQUIRED, VOICE_TRANSCRIPTION_FAILED, etc.")
    confirmation_required: bool = Field(default=False, description="Whether human confirmation gate is active")
    changes: List[Dict[str, Any]] = Field(default_factory=list, description="Proposed profile changes if confirmation required")
    text_fallback_available: bool = Field(default=True, description="Always true: text fallback is permanently available")
    duration_seconds: Optional[float] = Field(default=None, description="Audio duration in seconds")
    provider: str = Field(default="groq_whisper", description="STT provider used")
    stage: Optional[str] = Field(default=None, description="Current AgentState lifecycle stage")
    missing_information: List[str] = Field(default_factory=list, description="Remaining critical profile gaps")
    error_detail: Optional[str] = Field(default=None, description="Safe error detail if processing failed")


class SupportedLanguagesResponse(BaseModel):
    """Response schema for supported voice interaction languages."""
    supported_languages: List[str] = Field(default=["en", "hi", "te"])
    languages: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: LANGUAGE_METADATA)
