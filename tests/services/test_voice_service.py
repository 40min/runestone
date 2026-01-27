from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.services.voice_service import VoiceService


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.openai_api_key = "test_key"
    settings.voice_transcription_model = "whisper-1"
    settings.voice_enhancement_model = "gpt-4o-mini"
    return settings


@pytest.fixture
def mock_openai_client():
    with patch("runestone.services.voice_service.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock audio transcription
        mock_transcription = MagicMock()
        mock_transcription.text = "Hello world"
        mock_client.audio.transcriptions.create.return_value = mock_transcription

        # Mock chat completion for enhancement
        mock_completion = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Hello world."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_completion

        yield mock_client


@pytest.fixture
def voice_service(mock_settings, mock_openai_client):
    return VoiceService(mock_settings)


@pytest.mark.anyio
async def test_transcribe_audio_success(voice_service, mock_openai_client):
    """Test successful audio transcription."""
    audio_content = b"fake_audio_content"
    result = await voice_service.transcribe_audio(audio_content)

    assert result == "Hello world"
    mock_openai_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_openai_client.audio.transcriptions.create.call_args[1]
    assert call_kwargs["model"] == "whisper-1"
    assert "file" in call_kwargs
    assert "language" not in call_kwargs


@pytest.mark.anyio
async def test_transcribe_audio_with_language(voice_service, mock_openai_client):
    """Test audio transcription with explicit language."""
    audio_content = b"fake_audio_content"
    result = await voice_service.transcribe_audio(audio_content, language="sv")

    assert result == "Hello world"
    mock_openai_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_openai_client.audio.transcriptions.create.call_args[1]
    assert call_kwargs["language"] == "sv"


@pytest.mark.anyio
async def test_transcribe_audio_empty_response(voice_service, mock_openai_client):
    """Test transcription returning empty result."""
    mock_openai_client.audio.transcriptions.create.return_value.text = ""

    with pytest.raises(RunestoneError, match="Transcription returned empty result"):
        await voice_service.transcribe_audio(b"audio")


@pytest.mark.anyio
async def test_transcribe_audio_api_error(voice_service, mock_openai_client):
    """Test transcription API error."""
    mock_openai_client.audio.transcriptions.create.side_effect = Exception("API Error")

    with pytest.raises(RunestoneError, match="Failed to transcribe audio"):
        await voice_service.transcribe_audio(b"audio")


@pytest.mark.anyio
async def test_enhance_text_success(voice_service, mock_openai_client):
    """Test successful text enhancement."""
    original_text = "hello world"
    result = await voice_service.enhance_text(original_text)

    assert result == "Hello world."
    mock_openai_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert len(call_kwargs["messages"]) == 2
    assert call_kwargs["messages"][1]["content"] == original_text


@pytest.mark.anyio
async def test_enhance_text_empty_response(voice_service, mock_openai_client):
    """Test enhancement returning empty result (should return original)."""
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = ""

    result = await voice_service.enhance_text("original")
    assert result == "original"


@pytest.mark.anyio
async def test_enhance_text_api_error(voice_service, mock_openai_client):
    """Test enhancement API error (should return original)."""
    mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

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
