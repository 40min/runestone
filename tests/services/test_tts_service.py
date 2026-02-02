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


def test_synthesize_speech_stream(mock_settings):
    """Test streaming speech synthesis."""
    with patch("runestone.services.tts_service.OpenAI") as mock_openai:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = [b"chunk1", b"chunk2"]
        mock_openai.return_value.audio.speech.create.return_value = mock_response

        service = TTSService(mock_settings)
        chunks = list(service.synthesize_speech_stream("Hello"))

        assert chunks == [b"chunk1", b"chunk2"]
        mock_openai.return_value.audio.speech.create.assert_called_once_with(
            model="gpt-4o-mini-tts",
            voice="onyx",
            input="Hello",
            response_format="mp3",
            speed=1.0,
        )


@pytest.mark.anyio
async def test_push_audio_to_client_no_connection(mock_settings):
    """Test pushing audio when no WebSocket connection exists."""
    with patch("runestone.services.tts_service.OpenAI"):
        service = TTSService(mock_settings)

        # Should return silently if user_id not in connection_manager
        with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=None):
            await service.push_audio_to_client(user_id=1, text="Hello")


@pytest.mark.anyio
async def test_stream_audio_task_success(mock_settings):
    """Test successful audio push via WebSocket using internal task."""
    with patch("runestone.services.tts_service.OpenAI") as mock_openai:
        # Setup mock chunks
        mock_response = MagicMock()
        mock_response.iter_bytes.return_value = [b"chunk1"]
        mock_openai.return_value.audio.speech.create.return_value = mock_response

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
    service = TTSService(mock_settings)
    service._stream_audio_task = AsyncMock()

    await service.push_audio_to_client(user_id=1, text="Hello")

    # Check that a task was created and stored
    assert 1 in service._active_tasks
    task = service._active_tasks[1]
    import asyncio

    assert isinstance(task, asyncio.Task)
    await task  # Wait for it to finish
    service._stream_audio_task.assert_awaited_once_with(1, "Hello", 1.0)


@pytest.mark.anyio
async def test_push_audio_cancels_previous_task(mock_settings):
    """Test that new requests cancel previous ones."""
    service = TTSService(mock_settings)
    import asyncio

    # Create a slow task that we can spy on
    async def slow_task(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    service._stream_audio_task = AsyncMock(side_effect=slow_task)

    # Start first task
    await service.push_audio_to_client(user_id=1, text="First")
    task1 = service._active_tasks[1]

    # Start second task
    await service.push_audio_to_client(user_id=1, text="Second")
    task2 = service._active_tasks[1]

    assert task1 != task2
    # Yield to event loop to allow cancellation to propagate
    await asyncio.sleep(0)
    assert task1.cancelled()
    assert not task2.done()

    # cleanup
    task2.cancel()
