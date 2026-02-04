import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.services.tts_service import TTSService


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.openai_api_key = "fake-key"
    mock.tts_model = "gpt-4o-mini-tts"
    mock.tts_voice = "onyx"
    return mock


@pytest.mark.anyio
async def test_synthesize_speech_stream(mock_settings):
    """Test streaming speech synthesis."""
    with patch("runestone.services.tts_service.AsyncOpenAI") as mock_openai:
        # Setup mock response
        mock_response = MagicMock()

        # This is the async generator that will be returned by iter_bytes()
        async def aiter_contents():
            for chunk in [b"chunk1", b"chunk2"]:
                yield chunk

        # iter_bytes is a method that returns the async generator and accepts chunk_size
        def iter_bytes(*, chunk_size=4096):
            return aiter_contents()

        mock_response.iter_bytes = MagicMock(side_effect=iter_bytes)

        # Setup with_streaming_response.create as an async context manager
        mock_openai.return_value.audio.speech.with_streaming_response.create = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_openai.return_value.audio.speech.with_streaming_response.create.return_value = mock_ctx

        service = TTSService(mock_settings)
        chunks = []
        async for chunk in service.synthesize_speech_stream("Hello"):
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]
        mock_openai.return_value.audio.speech.with_streaming_response.create.assert_called_once_with(
            model="gpt-4o-mini-tts",
            voice="onyx",
            input="Hello",
            response_format="mp3",
            speed=1.0,
        )


@pytest.mark.anyio
async def test_push_audio_to_client_no_connection(mock_settings):
    """Test pushing audio when no WebSocket connection exists."""
    with patch("runestone.services.tts_service.AsyncOpenAI"):
        service = TTSService(mock_settings)

        # Should return silently if user_id not in connection_manager
        with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=None):
            await service.push_audio_to_client(user_id=1, text="Hello")


@pytest.mark.anyio
async def test_stream_audio_task_success(mock_settings):
    """Test successful audio push via WebSocket using internal task."""
    with patch("runestone.services.tts_service.AsyncOpenAI") as mock_openai:
        # Setup mock chunks
        mock_response = MagicMock()

        async def aiter_contents():
            yield b"chunk1"

        def iter_bytes(*, chunk_size=4096):
            return aiter_contents()

        mock_response.iter_bytes = MagicMock(side_effect=iter_bytes)

        # Setup with_streaming_response.create as an async context manager
        mock_openai.return_value.audio.speech.with_streaming_response.create = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_openai.return_value.audio.speech.with_streaming_response.create.return_value = mock_ctx

        service = TTSService(mock_settings)

        # Mock WebSocket
        mock_ws = MagicMock()
        mock_ws.send_bytes = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # patch connection_manager
        with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=mock_ws):
            await service._stream_audio_task(user_id=1, text="Hello")

        # Verify chunks sent
        assert mock_ws.send_bytes.await_count == 1
        mock_ws.send_bytes.assert_awaited_with(b"chunk1")
        assert mock_ws.send_json.await_count == 1
        mock_ws.send_json.assert_awaited_with({"status": "complete"})


@pytest.mark.anyio
async def test_push_audio_to_client_manages_task(mock_settings):
    """Test that push_audio_to_client creates a task."""
    with patch("runestone.services.tts_service.AsyncOpenAI"):
        service = TTSService(mock_settings)
        service._stream_audio_task = AsyncMock()

        await service.push_audio_to_client(user_id=1, text="Hello")

        # Check that a task was created and stored
        assert 1 in service._active_tasks
        task = service._active_tasks[1]
        assert isinstance(task, asyncio.Task)
        await task  # Wait for it to finish
        service._stream_audio_task.assert_awaited_once_with(1, "Hello", 1.0)


@pytest.mark.anyio
async def test_push_audio_cancels_previous_task(mock_settings):
    """Test that new requests cancel previous ones."""
    with patch("runestone.services.tts_service.AsyncOpenAI"):
        service = TTSService(mock_settings)

        # Create a slow task that we can spy on
        async def slow_task(*args, **kwargs):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                # Need to re-raise for task.cancelled() to be true
                raise

        service._stream_audio_task = AsyncMock(side_effect=slow_task)

        # Start first task
        await service.push_audio_to_client(user_id=1, text="First")
        task1 = service._active_tasks[1]

        # Start second task - this should await the cancellation of task1
        # To test this, we'll run it in a separate task and see it wait
        push_task = asyncio.create_task(service.push_audio_to_client(user_id=1, text="Second"))

        # Yield to allow task1 to be cancelled
        await asyncio.sleep(0.1)

        assert task1.cancelled()

        # Cleanup
        push_task.cancel()
        if 1 in service._active_tasks:
            service._active_tasks[1].cancel()
