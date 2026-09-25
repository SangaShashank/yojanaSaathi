"""
Yojana Saathi - Groq Integration Adapter
========================================
Adapter interface for GroqCloud Whisper API (voice/STT audio transcription preparation).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class GroqWhisperAdapter:
    """Adapter for GroqCloud audio transcription."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model_name = os.environ.get("WHISPER_MODEL", "whisper-large-v3")

    def transcribe_audio(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        """
        Transcribes speech audio bytes to text using Groq Whisper.
        Note: Full voice/STT workflow belongs to Phase 8.
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured.")
        # Prepared stub for Phase 8 integration
        logger.info(f"Groq Whisper transcription requested ({len(audio_bytes)} bytes)")
        return ""
