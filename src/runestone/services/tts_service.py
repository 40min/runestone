"""
Text-to-Speech service using OpenAI TTS API.

This module provides TTS functionality for synthesizing speech from text
and streaming it to clients via WebSocket.
"""

import asyncio
import logging
from typing import Iterator

from openai import OpenAI

from runestone.config import Settings
from runestone.core.connection_manager import connection_manager

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
        self._active_tasks: dict[int, asyncio.Task] = {}

    def synthesize_speech_stream(self, text: str, speed: float = 1.0) -> Iterator[bytes]:
        """
        Synthesize speech from text and yield audio chunks.

        Uses streaming to minimize latency - chunks are yielded as they arrive.

        Args:
            text: Text to synthesize into speech
            speed: Speed of the speech (0.25 to 4.0)

        Yields:
            Audio chunks as bytes (Opus format)

        Raises:
            Exception: If TTS API call fails
        """
        try:
            response = self._client.audio.speech.create(
                model=self.settings.tts_model,
                voice=self.settings.tts_voice,
                input=text,
                response_format="mp3",
                speed=speed,
            )
            for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise

    async def push_audio_to_client(self, user_id: int, text: str, speed: float = 1.0) -> None:
        """
        Schedule a task to push TTS audio to user's active WebSocket connection,
        canceling any existing task for that user.

        This method synthesizes speech from the given text and streams
        the audio chunks to the user via their WebSocket connection.
        If no active connection exists, the method returns silently.

        Args:
            user_id: ID of the user to push audio to
            text: Text to synthesize and stream
            speed: Speed of the speech
        """
        # Cancel active task
        if user_id in self._active_tasks:
            task = self._active_tasks[user_id]
            if not task.done():
                task.cancel()

        # Create new task
        task = asyncio.create_task(self._stream_audio_task(user_id, text, speed))
        self._active_tasks[user_id] = task

        def _cleanup(t: asyncio.Task):
            if self._active_tasks.get(user_id) == t:
                self._active_tasks.pop(user_id, None)

        task.add_done_callback(_cleanup)

    async def _stream_audio_task(self, user_id: int, text: str, speed: float = 1.0) -> None:
        """
        Internal task to synthesize and stream audio.
        """
        websocket = connection_manager.get_connection(user_id)
        if not websocket:
            logger.debug(f"No active WebSocket for user {user_id}, skipping TTS")
            return

        try:
            for chunk in self.synthesize_speech_stream(text, speed=speed):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"status": "complete"})
            logger.info(f"TTS audio pushed to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to push audio to user {user_id}: {e}")
