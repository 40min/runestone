"""
Voice transcription service.

This module provides voice-to-text transcription functionality
using OpenAI's Whisper API with optional text enhancement via GPT-4o-mini.
"""

import io
import logging

from openai import OpenAI

from runestone.config import Settings
from runestone.core.exceptions import RunestoneError

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for voice transcription and text enhancement."""

    def __init__(self, settings: Settings):
        """
        Initialize the voice service.

        Args:
            settings: Application settings containing model configuration
        """
        self.settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)

    async def transcribe_audio(self, audio_content: bytes) -> str:
        """
        Transcribe audio to text using OpenAI Whisper API.

        Args:
            audio_content: Raw audio bytes (WebM, WAV, MP3, etc. supported by Whisper)

        Returns:
            Transcribed text

        Raises:
            RunestoneError: If transcription fails
        """
        try:
            # Create a file-like object from bytes for the API
            audio_file = io.BytesIO(audio_content)
            audio_file.name = "recording.webm"

            response = self._client.audio.transcriptions.create(
                model=self.settings.voice_transcription_model,
                file=audio_file,
            )

            transcribed_text = response.text
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
            response = self._client.chat.completions.create(
                model=self.settings.voice_enhancement_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Fix grammar, punctuation, and clarity while preserving "
                            "the original meaning and tone. Return only the corrected text."
                            "The text is transcribed so could have some mistakes, please correct them."
                            "The text could be on several languages (Swedish, English, Russian)"
                        ),
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )

            enhanced_text = response.choices[0].message.content
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

    async def process_voice_input(self, audio_content: bytes, improve: bool = True) -> str:
        """
        Process voice input: transcribe and optionally enhance.

        Args:
            audio_content: Raw audio bytes
            improve: Whether to apply text enhancement

        Returns:
            Final transcribed (and optionally enhanced) text

        Raises:
            RunestoneError: If transcription fails
        """
        transcribed_text = await self.transcribe_audio(audio_content)
        logger.info(f"Transcribed audio to text: {transcribed_text}")

        if improve:
            return await self.enhance_text(transcribed_text)

        return transcribed_text
