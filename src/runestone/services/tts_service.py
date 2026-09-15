"""
Text-to-Speech orchestration service.

This module coordinates speech synthesis and streams audio to clients
via WebSocket. Provider-specific API calls live in voice clients.
"""

import asyncio
import logging
import time
from typing import AsyncIterator

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import VoiceSynthesisClient
from runestone.core.connection_manager import connection_manager
from runestone.core.error_tracking import capture_sanitized_exception, duration_bucket
from runestone.model_costs.tracking import CostTrackingHandle

logger = logging.getLogger(__name__)


class TTSService:
    """Service that orchestrates text-to-speech streaming to clients."""

    CANCELLATION_GRACE_SECONDS = 1.0

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
        self._active_cost_tracking: dict[int, CostTrackingHandle] = {}
        self._replacement_tasks: set[asyncio.Task] = set()
        # Global limit on concurrent synthesis requests to avoid overwhelming external providers.
        self._synthesis_semaphore = asyncio.Semaphore(5)

    def _telemetry(self, operation: str, started_at: float) -> dict[str, str]:
        """Return a configuration-only marker for a failed audio operation."""
        provider = self.settings.tts_provider
        model = self.settings.elevenlabs_tts_model if provider == "elevenlabs" else self.settings.tts_model
        return {
            "operation": operation,
            "outcome": "failed",
            "provider": provider,
            "model": model,
            "duration_bucket": duration_bucket(started_at),
        }

    async def synthesize_speech_stream(
        self,
        text: str,
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
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
        started_at = time.monotonic()
        try:
            # Backpressure: limit concurrent provider calls
            async with self._synthesis_semaphore:
                chunk_count = 0
                total_bytes = 0
                async for chunk in self._synthesis_client.synthesize_speech_stream(
                    text=text,
                    speed=speed,
                ):
                    chunk_count += 1
                    total_bytes += len(chunk)
                    yield chunk
                logger.debug(f"TTS synthesis finished: {chunk_count} chunks, {total_bytes} bytes yielded")
        except Exception:
            logger.error(
                "TTS synthesis failed",
                exc_info=True,
                extra={"runestone_telemetry": self._telemetry("tts_synthesis", started_at)},
            )
            raise

    async def push_audio_to_client(
        self,
        user_id: int,
        text: str,
        cost_tracking: CostTrackingHandle,
        speed: float = 1.0,
    ) -> None:
        """
        Schedule a task to push TTS audio to user's active WebSocket connection,
        canceling and waiting for any existing task for that user.

        Args:
            user_id: ID of the user to push audio to
            text: Text to synthesize and stream
            cost_tracking: Tracking handle registered for this background TTS request
            speed: Speed of the speech
        """
        new_task_scheduled = False
        previous_cost_tracking: CostTrackingHandle | None = None
        try:
            # Cancel and wait for active task to ensure serialization per user.
            if user_id in self._active_tasks:
                task = self._active_tasks[user_id]
                if not task.done():
                    previous_cost_tracking = self._active_cost_tracking[user_id]
                    self._replacement_tasks.add(task)
                    task.cancel()
                    done, _pending = await asyncio.wait({task}, timeout=self.CANCELLATION_GRACE_SECONDS)
                    if done:
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass
                    elif previous_cost_tracking.status is None:
                        previous_cost_tracking.finish("cancelled_with_unknown_usage")

                    # Cancellation can win before the coroutine is first polled.
                    if task.cancelled() and previous_cost_tracking.status is None:
                        previous_cost_tracking.finish("stale_replaced")

            stream_task = self._stream_audio_task(user_id, text, cost_tracking, speed)
            task = asyncio.create_task(stream_task)
            self._active_tasks[user_id] = task
            self._active_cost_tracking[user_id] = cost_tracking
            new_task_scheduled = True
        except asyncio.CancelledError:
            if not new_task_scheduled:
                if previous_cost_tracking is not None and previous_cost_tracking.status is None:
                    previous_cost_tracking.finish("cancelled_with_unknown_usage")
                cost_tracking.finish("cancelled")
            raise

        def _cleanup(t: asyncio.Task):
            # Clean up the task from tracking map if it's still the active one
            if self._active_tasks.get(user_id) == t:
                self._active_tasks.pop(user_id, None)
                self._active_cost_tracking.pop(user_id, None)
            self._replacement_tasks.discard(t)

            # Consume the result to handle any unhandled exceptions in the task coroutine
            try:
                if not t.cancelled():
                    t.result()
            except Exception as exception:
                # Logging only creates a sanitized breadcrumb. Capture an event at
                # the detached-task boundary while the exception is still available.
                capture_sanitized_exception(exception)
                logger.exception(f"Unhandled exception in TTS task for user {user_id}")

        task.add_done_callback(_cleanup)

    async def _stream_audio_task(
        self,
        user_id: int,
        text: str,
        cost_tracking: CostTrackingHandle,
        speed: float = 1.0,
    ) -> None:
        """
        Internal task to synthesize and stream audio.
        """
        terminal_status = "completed"
        started_at = time.monotonic()
        try:
            with cost_tracking.activate():
                websocket = connection_manager.get_connection(user_id)
                if not websocket:
                    terminal_status = "skipped_no_websocket"
                    logger.debug(f"No active WebSocket for user {user_id}, skipping TTS")
                    return

                stream = self.synthesize_speech_stream(text, speed=speed)
                try:
                    async for chunk in stream:
                        try:
                            await websocket.send_bytes(chunk)
                        except Exception:
                            logger.error(
                                "Audio delivery failed",
                                exc_info=True,
                                extra={"runestone_telemetry": self._telemetry("audio_delivery", started_at)},
                            )
                            raise
                finally:
                    await stream.aclose()
                try:
                    await websocket.send_json({"status": "complete"})
                except Exception:
                    logger.error(
                        "Audio delivery failed",
                        exc_info=True,
                        extra={"runestone_telemetry": self._telemetry("audio_delivery", started_at)},
                    )
                    raise
                logger.debug(f"TTS audio pushed to user {user_id}. All chunks sent.")
        except asyncio.CancelledError:
            terminal_status = "stale_replaced" if asyncio.current_task() in self._replacement_tasks else "cancelled"
            logger.debug(f"TTS task for user {user_id} was cancelled")
            raise
        except Exception:
            terminal_status = "failed"
            raise
        finally:
            cost_tracking.finish(terminal_status)
