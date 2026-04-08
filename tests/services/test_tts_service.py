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


@pytest.fixture
def mock_synthesis_client():
    """Create a mock synthesis client."""
    client = MagicMock()

    async def stream_chunks(text: str, speed: float = 1.0):
        for chunk in [b"chunk1", b"chunk2"]:
            yield chunk

    client.synthesize_speech_stream = MagicMock(side_effect=stream_chunks)
    return client


@pytest.mark.anyio
async def test_synthesize_speech_stream(mock_settings, mock_synthesis_client):
    """Test streaming speech synthesis."""
    service = TTSService(mock_settings, mock_synthesis_client)
    chunks = []
    async for chunk in service.synthesize_speech_stream("Hello"):
        chunks.append(chunk)

    assert chunks == [b"chunk1", b"chunk2"]
    mock_synthesis_client.synthesize_speech_stream.assert_called_once_with(text="Hello", speed=1.0)


@pytest.mark.anyio
async def test_push_audio_to_client_no_connection(mock_settings, mock_synthesis_client):
    """Test pushing audio when no WebSocket connection exists."""
    service = TTSService(mock_settings, mock_synthesis_client)

    # Should return silently if user_id not in connection_manager
    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=None):
        await service.push_audio_to_client(user_id=1, text="Hello")


@pytest.mark.anyio
async def test_stream_audio_task_success(mock_settings, mock_synthesis_client):
    """Test successful audio push via WebSocket using internal task."""

    async def stream_one_chunk(text: str, speed: float = 1.0):
        yield b"chunk1"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=stream_one_chunk)

    service = TTSService(mock_settings, mock_synthesis_client)

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
async def test_push_audio_to_client_manages_task(mock_settings, mock_synthesis_client):
    """Test that push_audio_to_client creates a task."""
    service = TTSService(mock_settings, mock_synthesis_client)
    service._stream_audio_task = AsyncMock()

    await service.push_audio_to_client(user_id=1, text="Hello")

    # Check that a task was created and stored
    assert 1 in service._active_tasks
    task = service._active_tasks[1]
    assert isinstance(task, asyncio.Task)
    await task  # Wait for it to finish
    service._stream_audio_task.assert_awaited_once_with(1, "Hello", 1.0)


@pytest.mark.anyio
async def test_push_audio_cancels_previous_task(mock_settings, mock_synthesis_client):
    """Test that new requests cancel previous ones."""
    service = TTSService(mock_settings, mock_synthesis_client)

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
