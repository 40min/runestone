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
        )


@pytest.mark.anyio
async def test_push_audio_to_client_no_connection(mock_settings):
    """Test pushing audio when no WebSocket connection exists."""
    with patch("runestone.services.tts_service.OpenAI"):
        service = TTSService(mock_settings)

        # Should return silently if user_id not in active_connections
        with patch("runestone.api.audio_ws.active_connections", {}):
            await service.push_audio_to_client(user_id=1, text="Hello")


@pytest.mark.anyio
async def test_push_audio_to_client_success(mock_settings):
    """Test successful audio push via WebSocket."""
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

        # patch active_connections
        with patch("runestone.api.audio_ws.active_connections", {1: mock_ws}):
            await service.push_audio_to_client(user_id=1, text="Hello")

        # Verify chunks sent
        assert mock_ws.send_bytes.await_count == 1
        mock_ws.send_bytes.assert_awaited_with(b"chunk1")
        assert mock_ws.send_json.await_count == 1
        mock_ws.send_json.assert_awaited_with({"status": "complete"})
