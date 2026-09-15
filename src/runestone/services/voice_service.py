"""
Voice transcription service.

This module provides voice-to-text transcription functionality
with optional transcript cleanup. Provider-specific API calls live
in voice clients.
"""

import logging
import time

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import VoiceEnhancementClient, VoiceTranscriptionClient
from runestone.core.constants import LANGUAGE_CODE_MAP
from runestone.core.error_tracking import duration_bucket
from runestone.core.exceptions import RunestoneError
from runestone.model_costs.tracking import track_model_costs

logger = logging.getLogger(__name__)


class VoiceService:
    """Service coordinating speech-to-text and optional transcript cleanup."""

    def __init__(
        self,
        settings: Settings,
        transcription_client: VoiceTranscriptionClient,
        enhancement_client: VoiceEnhancementClient,
    ):
        """
        Initialize the voice service.

        Args:
            settings: Application settings containing model configuration
            transcription_client: Provider client handling raw transcription
            enhancement_client: Provider client handling transcript cleanup
        """
        self.settings = settings
        self._transcription_client = transcription_client
        self._enhancement_client = enhancement_client

    def _transcription_telemetry(self, started_at: float, outcome: str) -> dict[str, str]:
        """Return the configuration-only marker for a transcription outcome."""
        return {
            "operation": "voice_transcription",
            "outcome": outcome,
            "provider": self.settings.voice_transcription_provider,
            "model": self.settings.voice_transcription_model,
            "duration_bucket": duration_bucket(started_at),
        }

    def _enhancement_telemetry(self, started_at: float, outcome: str) -> dict[str, str]:
        """Return the configuration-only marker for transcript cleanup."""
        return {
            "operation": "voice_enhancement",
            "outcome": outcome,
            "provider": "openai",
            "model": self.settings.voice_enhancement_model,
            "duration_bucket": duration_bucket(started_at),
        }

    async def transcribe_audio(
        self,
        audio_content: bytes,
        language: str | None = None,
    ) -> str:
        """
        Transcribe audio to text using the configured transcription provider.

        Args:
            audio_content: Raw audio bytes from the browser recorder (currently WebM Opus)
            language: Optional ISO-639-1 language code
        Returns:
            Transcribed text

        Raises:
            RunestoneError: If transcription fails
        """
        started_at = time.monotonic()
        try:
            transcribed_text = await self._transcription_client.transcribe_audio(
                audio_content=audio_content,
                language=language,
            )
            if not transcribed_text:
                logger.error(
                    "Voice transcription returned empty result",
                    extra={"runestone_telemetry": self._transcription_telemetry(started_at, "empty_result")},
                )
                raise RunestoneError("Transcription returned empty result")

            logger.info(f"Transcribed {len(audio_content)} bytes to {len(transcribed_text)} characters")
            return transcribed_text.strip()

        except RunestoneError:
            raise
        except Exception as error:
            logger.error(
                "Voice transcription failed",
                exc_info=True,
                extra={"runestone_telemetry": self._transcription_telemetry(started_at, "failed")},
            )
            raise RunestoneError(f"Failed to transcribe audio: {str(error)}")

    async def enhance_text(
        self,
        text: str,
    ) -> str:
        """
        Enhance transcribed text for grammar and clarity.

        Args:
            text: The transcribed text to enhance
        Returns:
            Enhanced text with improved grammar and clarity

        Raises:
            RunestoneError: If enhancement fails
        """
        started_at = time.monotonic()
        try:
            system_prompt = (
                "Fix grammar, punctuation, and clarity while preserving "
                "the original meaning and tone. Return only the corrected text."
                "The text is transcribed so could have some mistakes, please correct them."
            )
            enhanced_text = await self._enhancement_client.enhance_text(
                text=text,
                system_prompt=system_prompt,
            )
            if not enhanced_text:
                logger.warning(
                    "Voice enhancement returned empty result; using original text",
                    extra={"runestone_telemetry": self._enhancement_telemetry(started_at, "fallback_original")},
                )
                return text

            logger.info(f"Enhanced text from {len(text)} to {len(enhanced_text)} characters")
            return enhanced_text.strip()

        except Exception:
            logger.error(
                "Voice enhancement failed",
                exc_info=True,
                extra={"runestone_telemetry": self._enhancement_telemetry(started_at, "fallback_original")},
            )
            # For enhancement, we can gracefully degrade to unenhanced text
            return text

    async def process_voice_input(self, audio_content: bytes, improve: bool = True, language: str | None = None) -> str:
        """
        Process voice input:
        1. Transcribe audio with the configured STT provider
        2. Optionally enhance text with the configured cleanup model

        Args:
            audio_content: Raw audio bytes
            improve: Whether to apply text enhancement
            language: Optional full language name or ISO-639-1 code (e.g., from user profile)

        Returns:
            Final processed text
        """
        async with track_model_costs("voice_transcription"):
            whisper_lang = language
            if language and language in LANGUAGE_CODE_MAP:
                whisper_lang = LANGUAGE_CODE_MAP[language]
                logger.info("Mapped voice language to ISO-639-1 code")

            transcribed_text = await self.transcribe_audio(
                audio_content,
                language=whisper_lang,
            )
            logger.info("Voice transcription completed language=%s", whisper_lang)

            if not improve:
                return transcribed_text

            return await self.enhance_text(
                transcribed_text,
            )
