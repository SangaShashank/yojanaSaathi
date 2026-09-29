"""
Yojana Saathi - Speech-to-Text & Groq Integration Provider
===========================================================
Provides an extensible SpeechToTextProvider abstraction and Groq-hosted Whisper
implementation for Phase 8 Multilingual Voice & Audio.
"""

from abc import ABC, abstractmethod
import io
import logging
import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()
logger = logging.getLogger(__name__)

# Canonical language normalization mapping
LANGUAGE_MAP = {
    "english": "en",
    "en": "en",
    "hindi": "hi",
    "hi": "hi",
    "telugu": "te",
    "te": "te",
}


class SpeechToTextResult(BaseModel):
    """Structured Speech-to-Text transcription output and metadata."""
    model_config = ConfigDict(extra="allow")

    transcript: str
    language: Optional[str] = "en"
    detected_language: Optional[str] = None
    provider: str = "groq_whisper"
    duration_seconds: Optional[float] = None
    confidence: Optional[float] = None  # None if not provided by vendor


class SpeechToTextError(Exception):
    """Base exception for speech-to-text processing failures."""
    pass


class SpeechToTextUnavailableError(SpeechToTextError):
    """Raised when the STT provider is unavailable (missing key, connection failure)."""
    pass


class SpeechToTextProvider(ABC):
    """Abstract base class for all STT providers in Yojana Saathi."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: Optional[str] = None,
    ) -> SpeechToTextResult:
        """
        Transcribes speech audio bytes to text.
        Must return structured SpeechToTextResult or raise SpeechToTextError.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is properly configured and reachable."""
        pass


class GroqWhisperProvider(SpeechToTextProvider):
    """Production STT provider using GroqCloud hosted Whisper."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model_name = model_name or os.environ.get("WHISPER_MODEL", "whisper-large-v3")
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise SpeechToTextUnavailableError(
                    "GROQ_API_KEY is not configured in the environment. STT unavailable."
                )
            try:
                import groq
                self._client = groq.Groq(api_key=self.api_key)
            except Exception as e:
                raise SpeechToTextUnavailableError(f"Failed to initialize Groq client: {e}")
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: Optional[str] = None,
    ) -> SpeechToTextResult:
        if not audio_bytes:
            raise SpeechToTextError("Audio bytes cannot be empty.")

        if not self.is_available():
            raise SpeechToTextUnavailableError("Groq STT is not configured (missing GROQ_API_KEY).")

        client = self._get_client()

        # Map language code to ISO code acceptable by Whisper
        whisper_lang = language.lower() if language else None
        if whisper_lang in ["hi", "hindi"]:
            whisper_lang = "hi"
        elif whisper_lang in ["te", "telugu"]:
            whisper_lang = "te"
        elif whisper_lang in ["en", "english"]:
            whisper_lang = "en"
        else:
            whisper_lang = None

        try:
            logger.info(
                f"Invoking Groq Whisper STT (model={self.model_name}, "
                f"bytes={len(audio_bytes)}, requested_lang={language})"
            )
            # Invoke Groq API with in-memory file tuple
            response = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=self.model_name,
                language=whisper_lang,
                response_format="verbose_json",
            )

            raw_text = getattr(response, "text", "") or ""
            raw_detected_lang = getattr(response, "language", None)
            raw_duration = getattr(response, "duration", None)

            # Normalize detected language
            norm_detected = None
            if raw_detected_lang:
                norm_detected = LANGUAGE_MAP.get(str(raw_detected_lang).strip().lower(), str(raw_detected_lang).lower())

            resolved_lang = norm_detected or language or "en"
            duration_val = float(raw_duration) if raw_duration is not None else None

            return SpeechToTextResult(
                transcript=raw_text.strip(),
                language=language or resolved_lang,
                detected_language=norm_detected,
                provider="groq_whisper",
                duration_seconds=duration_val,
                confidence=None,
            )

        except SpeechToTextUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Groq Whisper transcription failed: {e}", exc_info=True)
            raise SpeechToTextError(f"STT transcription failed: {e}")


class MockSpeechToTextProvider(SpeechToTextProvider):
    """
    Deterministic mock provider for testing multilingual workflows and failure states
    without making real external API calls.
    """

    def __init__(
        self,
        mock_transcript: str = "I am a farmer from Telangana and have 3 acres.",
        language: str = "en",
        detected_language: Optional[str] = None,
        duration_seconds: float = 2.5,
        available: bool = True,
        simulate_failure: bool = False,
    ):
        self.mock_transcript = mock_transcript
        self.language = language
        self.detected_language = detected_language or language
        self.duration_seconds = duration_seconds
        self.available = available
        self.simulate_failure = simulate_failure

    def is_available(self) -> bool:
        return self.available

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: Optional[str] = None,
    ) -> SpeechToTextResult:
        if not self.available or self.simulate_failure:
            raise SpeechToTextUnavailableError("Mock STT provider is unavailable.")
        if not audio_bytes:
            raise SpeechToTextError("Audio bytes cannot be empty.")

        return SpeechToTextResult(
            transcript=self.mock_transcript,
            language=language or self.language,
            detected_language=self.detected_language,
            provider="mock_stt",
            duration_seconds=self.duration_seconds,
            confidence=None,
        )


class GroqWhisperAdapter:
    """Backwards-compatible adapter wrapping GroqWhisperProvider."""

    def __init__(self, api_key: Optional[str] = None):
        self.provider = GroqWhisperProvider(api_key=api_key)

    def transcribe_audio(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        res = self.provider.transcribe(audio_bytes, language=language)
        return res.transcript
