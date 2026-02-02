"""
Text-to-Speech service using OpenAI TTS API.

This module provides TTS functionality for synthesizing speech from text
and streaming it to clients via WebSocket.
"""

import logging
from typing import Iterator

from openai import OpenAI

from runestone.config import Settings

logger = logging.getLogger(__name__)


class TTSService:
    """Service for text-to-speech synthesis using OpenAI TTS."""

    def __init__(self, settings: Settings):
        """
        Initialize the TTS service.

        Args:
            settings: Application settings containing TTS configuration
        """
        self.settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)

    def synthesize_speech_stream(self, text: str) -> Iterator[bytes]:
        """
        Synthesize speech from text and yield audio chunks.

        Uses streaming to minimize latency - chunks are yielded as they arrive.

        Args:
            text: Text to synthesize into speech

        Yields:
            Audio chunks as bytes (MP3 format)

        Raises:
            Exception: If TTS API call fails
        """
        try:
            response = self._client.audio.speech.create(
                model=self.settings.tts_model,
                voice=self.settings.tts_voice,
                input=text,
                response_format="mp3",
            )
            for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise

    async def push_audio_to_client(self, user_id: int, text: str) -> None:
        """
        Push TTS audio to user's active WebSocket connection.

        This method synthesizes speech from the given text and streams
        the audio chunks to the user via their WebSocket connection.
        If no active connection exists, the method returns silently.

        Args:
            user_id: ID of the user to push audio to
            text: Text to synthesize and stream
        """
        from runestone.api.audio_ws import active_connections

        websocket = active_connections.get(user_id)
        if not websocket:
            logger.debug(f"No active WebSocket for user {user_id}, skipping TTS")
            return

        try:
            for chunk in self.synthesize_speech_stream(text):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"status": "complete"})
            logger.info(f"TTS audio pushed to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to push audio to user {user_id}: {e}")
