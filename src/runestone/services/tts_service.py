"""
Text-to-Speech orchestration service.

This module coordinates speech synthesis and streams audio to clients
via WebSocket. Provider-specific API calls live in voice clients.
"""

import asyncio
import logging
from typing import AsyncIterator

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import VoiceSynthesisClient
from runestone.core.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class TTSService:
    """Service that orchestrates text-to-speech streaming to clients."""

    def __init__(self, settings: Settings, synthesis_client: VoiceSynthesisClient):
        """
        Initialize the TTS service.

        Args:
            settings: Application settings containing TTS configuration
            synthesis_client: Provider client that performs speech synthesis
        """
        self.settings = settings
        self._synthesis_client = synthesis_client
        self._active_tasks: dict[int, asyncio.Task] = {}
        # Global limit on concurrent synthesis requests to avoid overwhelming external providers.
        self._synthesis_semaphore = asyncio.Semaphore(5)

    async def synthesize_speech_stream(self, text: str, speed: float = 1.0) -> AsyncIterator[bytes]:
        """
        Synthesize speech from text and yield audio chunks.

        Uses streaming to minimize latency - chunks are yielded as they arrive.

        Args:
            text: Text to synthesize into speech
            speed: Speed of the speech (0.25 to 4.0)

        Yields:
            Audio chunks as bytes (mp3 format)

        Raises:
            Exception: If TTS API call fails
        """
        try:
            # Backpressure: limit concurrent provider calls
            async with self._synthesis_semaphore:
                chunk_count = 0
                total_bytes = 0
                async for chunk in self._synthesis_client.synthesize_speech_stream(text=text, speed=speed):
                    chunk_count += 1
                    total_bytes += len(chunk)
                    yield chunk
                logger.debug(f"TTS synthesis finished: {chunk_count} chunks, {total_bytes} bytes yielded")
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise

    async def push_audio_to_client(self, user_id: int, text: str, speed: float = 1.0) -> None:
        """
        Schedule a task to push TTS audio to user's active WebSocket connection,
        canceling and waiting for any existing task for that user.

        Args:
            user_id: ID of the user to push audio to
            text: Text to synthesize and stream
            speed: Speed of the speech
        """
        # Cancel and wait for active task to ensure serialization per user
        if user_id in self._active_tasks:
            task = self._active_tasks[user_id]
            if not task.done():
                task.cancel()
                try:
                    # Wait for the task to finish its cancellation to avoid interleaving audio
                    await task
                except (asyncio.CancelledError, Exception):
                    # Exception or cancellation is expected here
                    pass

        # Create new task
        task = asyncio.create_task(self._stream_audio_task(user_id, text, speed))
        self._active_tasks[user_id] = task

        def _cleanup(t: asyncio.Task):
            # Clean up the task from tracking map if it's still the active one
            if self._active_tasks.get(user_id) == t:
                self._active_tasks.pop(user_id, None)

            # Consume the result to handle any unhandled exceptions in the task coroutine
            try:
                if not t.cancelled():
                    t.result()
            except Exception:
                # Exceptions inside _stream_audio_task should already be logged,
                # but this ensures no "Task exception was never retrieved" warning.
                logger.exception(f"Unhandled exception in TTS task for user {user_id}")

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
            async for chunk in self.synthesize_speech_stream(text, speed=speed):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"status": "complete"})
            logger.debug(f"TTS audio pushed to user {user_id}. All chunks sent.")
        except asyncio.CancelledError:
            logger.debug(f"TTS task for user {user_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Failed to push audio to user {user_id}: {e}")
            # Re-raise to let the done_callback see the exception if needed,
            # though we already logged it.
            raise
