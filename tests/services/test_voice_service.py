from unittest.mock import AsyncMock, MagicMock

import pytest

from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.services.voice_service import VoiceService


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.voice_transcription_model = "whisper-1"
    settings.voice_enhancement_model = "gpt-4o-mini"
    return settings


@pytest.fixture
def mock_transcription_client():
    client = MagicMock()
    client.transcribe_audio = AsyncMock(return_value="Hello world")
    return client


@pytest.fixture
def mock_enhancement_client():
    client = MagicMock()
    client.enhance_text = AsyncMock(return_value="Hello world.")
    return client


@pytest.fixture
def voice_service(mock_settings, mock_transcription_client, mock_enhancement_client):
    return VoiceService(mock_settings, mock_transcription_client, mock_enhancement_client)


@pytest.mark.anyio
async def test_transcribe_audio_success(voice_service, mock_transcription_client):
    """Test successful audio transcription."""
    audio_content = b"fake_audio_content"
    result = await voice_service.transcribe_audio(audio_content)

    assert result == "Hello world"
    mock_transcription_client.transcribe_audio.assert_awaited_once_with(audio_content=audio_content, language=None)


@pytest.mark.anyio
async def test_transcribe_audio_with_language(voice_service, mock_transcription_client):
    """Test audio transcription with explicit language."""
    audio_content = b"fake_audio_content"
    result = await voice_service.transcribe_audio(audio_content, language="sv")

    assert result == "Hello world"
    mock_transcription_client.transcribe_audio.assert_awaited_once_with(audio_content=audio_content, language="sv")


@pytest.mark.anyio
async def test_transcribe_audio_empty_response(voice_service, mock_transcription_client):
    """Test transcription returning empty result."""
    mock_transcription_client.transcribe_audio.return_value = ""

    with pytest.raises(RunestoneError, match="Transcription returned empty result"):
        await voice_service.transcribe_audio(b"audio")


@pytest.mark.anyio
async def test_transcribe_audio_api_error(voice_service, mock_transcription_client):
    """Test transcription API error."""
    mock_transcription_client.transcribe_audio.side_effect = Exception("API Error")

    with pytest.raises(RunestoneError, match="Failed to transcribe audio"):
        await voice_service.transcribe_audio(b"audio")


@pytest.mark.anyio
async def test_enhance_text_success(voice_service, mock_enhancement_client):
    """Test successful text enhancement."""
    original_text = "hello world"
    result = await voice_service.enhance_text(original_text)

    assert result == "Hello world."
    assert mock_enhancement_client.enhance_text.await_count == 1
    call_kwargs = mock_enhancement_client.enhance_text.call_args.kwargs
    assert call_kwargs["text"] == original_text
    assert "Fix grammar, punctuation, and clarity" in call_kwargs["system_prompt"]


@pytest.mark.anyio
async def test_enhance_text_empty_response(voice_service, mock_enhancement_client):
    """Test enhancement returning empty result (should return original)."""
    mock_enhancement_client.enhance_text.return_value = ""

    result = await voice_service.enhance_text("original")
    assert result == "original"


@pytest.mark.anyio
async def test_enhance_text_api_error(voice_service, mock_enhancement_client):
    """Test enhancement API error (should return original)."""
    mock_enhancement_client.enhance_text.side_effect = Exception("API Error")

    result = await voice_service.enhance_text("original")
    assert result == "original"


@pytest.mark.anyio
async def test_process_voice_input_auto_detection(voice_service):
    """Test the voice processing pipeline with auto-detection (language=None)."""
    voice_service.transcribe_audio = AsyncMock(return_value="raw text")
    voice_service.enhance_text = AsyncMock(return_value="enhanced text")

    audio_content = b"audio"
    result = await voice_service.process_voice_input(audio_content, improve=True, language=None)

    assert result == "enhanced text"
    voice_service.transcribe_audio.assert_called_once_with(audio_content, language=None)
    voice_service.enhance_text.assert_called_once_with("raw text")


@pytest.mark.anyio
async def test_process_voice_input_with_provided_language(voice_service):
    """Test the voice processing pipeline with a specific language."""
    voice_service.transcribe_audio = AsyncMock(return_value="raw text")
    voice_service.enhance_text = AsyncMock(return_value="enhanced text")

    audio_content = b"audio"
    result = await voice_service.process_voice_input(audio_content, improve=True, language="sv")

    assert result == "enhanced text"
    voice_service.transcribe_audio.assert_called_once_with(audio_content, language="sv")
    voice_service.enhance_text.assert_called_once_with("raw text")


@pytest.mark.anyio
async def test_process_voice_input_without_improve(voice_service):
    """Test pipeline without enhancement."""
    voice_service.transcribe_audio = AsyncMock(return_value="raw text")
    voice_service.enhance_text = AsyncMock()

    result = await voice_service.process_voice_input(b"audio", improve=False)

    assert result == "raw text"
    voice_service.enhance_text.assert_not_called()
    voice_service.transcribe_audio.assert_called_once()


@pytest.mark.anyio
async def test_process_voice_input_with_language_mapping(voice_service):
    """Test that full language names are mapped to ISO-639-1 codes."""
    voice_service.transcribe_audio = AsyncMock(return_value="raw text")
    voice_service.enhance_text = AsyncMock(return_value="enhanced text")

    audio_content = b"audio"
    # "Swedish" should map to "sv"
    result = await voice_service.process_voice_input(audio_content, improve=True, language="Swedish")

    assert result == "enhanced text"
    # Verify it was called with "sv" not "Swedish"
    voice_service.transcribe_audio.assert_called_once_with(audio_content, language="sv")
