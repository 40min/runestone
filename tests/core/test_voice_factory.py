"""Tests for voice client factory helpers."""

from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import create_voice_synthesis_client, create_voice_transcription_client
from runestone.core.exceptions import RunestoneError


@patch("runestone.core.clients.voice.voice_factory._create_openai_voice_client")
def test_create_voice_transcription_client_openai(mock_create_openai):
    """OpenAI transcription provider should resolve to OpenAI voice client."""
    settings = Mock(spec=Settings)
    settings.voice_transcription_provider = "openai"
    expected = Mock()
    mock_create_openai.return_value = expected

    result = create_voice_transcription_client(settings)

    assert result is expected
    mock_create_openai.assert_called_once_with(settings)


def test_create_voice_transcription_client_elevenlabs_not_implemented():
    """ElevenLabs transcription provider is intentionally not available in phase 1."""
    settings = Mock(spec=Settings)
    settings.voice_transcription_provider = "elevenlabs"

    with pytest.raises(RunestoneError, match="VOICE_TRANSCRIPTION_PROVIDER=elevenlabs is not implemented yet"):
        create_voice_transcription_client(settings)


@patch("runestone.core.clients.voice.voice_factory._create_openai_voice_client")
def test_create_voice_synthesis_client_openai(mock_create_openai):
    """OpenAI TTS provider should resolve to OpenAI voice client."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "openai"
    expected = Mock()
    mock_create_openai.return_value = expected

    result = create_voice_synthesis_client(settings)

    assert result is expected
    mock_create_openai.assert_called_once_with(settings)


@patch("runestone.core.clients.voice.voice_factory._create_elevenlabs_voice_client")
def test_create_voice_synthesis_client_elevenlabs(mock_create_elevenlabs):
    """ElevenLabs TTS provider should resolve to ElevenLabs voice client."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "elevenlabs"
    expected = Mock()
    mock_create_elevenlabs.return_value = expected

    result = create_voice_synthesis_client(settings)

    assert result is expected
    mock_create_elevenlabs.assert_called_once_with(settings)
