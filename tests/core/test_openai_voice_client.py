"""Tests for the OpenAI voice client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from runestone.core.clients.voice.openai_voice_client import OpenAIVoiceClient
from runestone.core.exceptions import APIKeyError


@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
def test_instantiation_requires_api_key(mock_async_openai):
    """Client should reject missing API key."""
    with pytest.raises(APIKeyError, match="OpenAI API key is required"):
        OpenAIVoiceClient(
            api_key="",
            transcription_model="whisper-1",
            enhancement_model="gpt-4o-mini",
            tts_model="gpt-4o-mini-tts",
            tts_voice="alloy",
        )

    mock_async_openai.assert_not_called()


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_transcribe_audio_uses_async_client(mock_async_openai):
    """Transcription should call the async OpenAI client."""
    mock_client = mock_async_openai.return_value
    mock_client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(text=" hello "))

    client = OpenAIVoiceClient(
        api_key="test-key",
        transcription_model="whisper-1",
        enhancement_model="gpt-4o-mini",
        tts_model="gpt-4o-mini-tts",
        tts_voice="alloy",
    )

    result = await client.transcribe_audio(b"audio-bytes", language="sv")

    assert result == "hello"
    mock_client.audio.transcriptions.create.assert_awaited_once()
    call_kwargs = mock_client.audio.transcriptions.create.await_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["language"] == "sv"
    assert call_kwargs["file"].name == "recording.webm"


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_enhance_text_uses_async_client(mock_async_openai):
    """Enhancement should call the async OpenAI chat client."""
    mock_client = mock_async_openai.return_value
    mock_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" enhanced text "))])
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    client = OpenAIVoiceClient(
        api_key="test-key",
        transcription_model="whisper-1",
        enhancement_model="gpt-4o-mini",
        tts_model="gpt-4o-mini-tts",
        tts_voice="alloy",
    )

    result = await client.enhance_text("raw text", "fix grammar")

    assert result == "enhanced text"
    mock_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "fix grammar"},
            {"role": "user", "content": "raw text"},
        ],
    )
