"""
Voice transcription service.

This module provides voice-to-text transcription functionality
with optional transcript cleanup. Provider-specific API calls live
in voice clients.
"""

import logging

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import VoiceTranscriptionClient
from runestone.core.constants import LANGUAGE_CODE_MAP
from runestone.core.exceptions import RunestoneError

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for voice transcription and text enhancement."""

    def __init__(self, settings: Settings, transcription_client: VoiceTranscriptionClient):
        """
        Initialize the voice service.

        Args:
            settings: Application settings containing model configuration
            transcription_client: Provider client handling transcription and enhancement
        """
        self.settings = settings
        self._transcription_client = transcription_client

    async def transcribe_audio(self, audio_content: bytes, language: str | None = None) -> str:
        """
        Transcribe audio to text using the configured transcription provider.

        Args:
            audio_content: Raw audio bytes (WebM, WAV, MP3, etc. supported by Whisper)
            language: Optional ISO-639-1 language code

        Returns:
            Transcribed text

        Raises:
            RunestoneError: If transcription fails
        """
        try:
            transcribed_text = await self._transcription_client.transcribe_audio(
                audio_content=audio_content,
                language=language,
            )
            if not transcribed_text:
                raise RunestoneError("Transcription returned empty result")

            logger.info(f"Transcribed {len(audio_content)} bytes to {len(transcribed_text)} characters")
            return transcribed_text.strip()

        except RunestoneError:
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise RunestoneError(f"Failed to transcribe audio: {str(e)}")

    async def enhance_text(self, text: str) -> str:
        """
        Enhance transcribed text for grammar and clarity.

        Args:
            text: The transcribed text to enhance

        Returns:
            Enhanced text with improved grammar and clarity

        Raises:
            RunestoneError: If enhancement fails
        """
        try:
            system_prompt = (
                "Fix grammar, punctuation, and clarity while preserving "
                "the original meaning and tone. Return only the corrected text."
                "The text is transcribed so could have some mistakes, please correct them."
            )
            enhanced_text = await self._transcription_client.enhance_text(
                text=text,
                system_prompt=system_prompt,
            )
            if not enhanced_text:
                logger.warning("Enhancement returned empty result, using original text")
                return text

            logger.info(f"Enhanced text from {len(text)} to {len(enhanced_text)} characters")
            return enhanced_text.strip()

        except Exception as e:
            logger.error(f"Text enhancement failed: {e}", exc_info=True)
            # For enhancement, we can gracefully degrade to unenhanced text
            logger.warning("Falling back to unenhanced text")
            return text

    async def process_voice_input(self, audio_content: bytes, improve: bool = True, language: str | None = None) -> str:
        """
        Process voice input:
        1. Transcribe audio (Whisper handles auto-detection if language is None)
        2. Optionally enhance text with GPT

        Args:
            audio_content: Raw audio bytes
            improve: Whether to apply text enhancement
            language: Optional full language name or ISO-639-1 code (e.g., from user profile)

        Returns:
            Final processed text
        """
        # Map full language name to ISO-639-1 if possible
        whisper_lang = language
        if language and language in LANGUAGE_CODE_MAP:
            whisper_lang = LANGUAGE_CODE_MAP[language]
            logger.info(f"Mapped language '{language}' to code '{whisper_lang}'")

        # 1. Transcribe (with provided language or Whisper auto-detection)
        transcribed_text = await self.transcribe_audio(audio_content, language=whisper_lang)
        logger.info(f"Transcription completed (lang={whisper_lang}): {transcribed_text}")

        # 2. Text enhancement
        if improve:
            return await self.enhance_text(transcribed_text)

        return transcribed_text
