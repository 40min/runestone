"""Tests for voice client factory helpers."""

from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.clients.voice.voice_factory import (
    create_voice_enhancement_client,
    create_voice_synthesis_client,
    create_voice_transcription_client,
)
from runestone.core.exceptions import APIKeyError, RunestoneError


@patch("runestone.core.clients.voice.voice_factory._create_openai_stt_client")
def test_create_voice_transcription_client_openai(mock_create_openai_stt):
    """OpenAI transcription provider should resolve to OpenAI voice client."""
    settings = Mock(spec=Settings)
    settings.voice_transcription_provider = "openai"
    expected = Mock()
    mock_create_openai_stt.return_value = expected

    result = create_voice_transcription_client(settings)

    assert result is expected
    mock_create_openai_stt.assert_called_once_with(settings)


@patch("runestone.core.clients.voice.voice_factory._create_elevenlabs_stt_client")
def test_create_voice_transcription_client_elevenlabs(mock_create_elevenlabs_stt):
    """ElevenLabs transcription provider should resolve to ElevenLabs voice client."""
    settings = Mock(spec=Settings)
    settings.voice_transcription_provider = "elevenlabs"
    expected = Mock()
    mock_create_elevenlabs_stt.return_value = expected

    result = create_voice_transcription_client(settings)

    assert result is expected
    mock_create_elevenlabs_stt.assert_called_once_with(settings)


@patch("runestone.core.clients.voice.voice_factory._create_openai_enhancement_client")
def test_create_voice_enhancement_client_uses_openai(mock_create_openai_enhancement):
    """Transcript cleanup should stay on OpenAI regardless of raw STT provider."""
    settings = Mock(spec=Settings)
    expected = Mock()
    mock_create_openai_enhancement.return_value = expected

    result = create_voice_enhancement_client(settings)

    assert result is expected
    mock_create_openai_enhancement.assert_called_once_with(settings)


@patch("runestone.core.clients.voice.voice_factory._create_openai_tts_client")
def test_create_voice_synthesis_client_openai(mock_create_openai_tts):
    """OpenAI TTS provider should resolve to OpenAI voice client."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "openai"
    expected = Mock()
    mock_create_openai_tts.return_value = expected

    result = create_voice_synthesis_client(settings)

    assert result is expected
    mock_create_openai_tts.assert_called_once_with(settings)


@patch("runestone.core.clients.voice.voice_factory._create_elevenlabs_tts_client")
def test_create_voice_synthesis_client_elevenlabs(mock_create_elevenlabs_tts):
    """ElevenLabs TTS provider should resolve to ElevenLabs voice client."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "elevenlabs"
    expected = Mock()
    mock_create_elevenlabs_tts.return_value = expected

    result = create_voice_synthesis_client(settings)

    assert result is expected
    mock_create_elevenlabs_tts.assert_called_once_with(settings)


def test_create_voice_synthesis_client_elevenlabs_requires_voice_id():
    """Factory should fail fast when ElevenLabs API key is missing."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "elevenlabs"
    settings.elevenlabs_api_key = None

    with pytest.raises(APIKeyError, match="ElevenLabs API key is required"):
        create_voice_synthesis_client(settings)


def test_create_voice_synthesis_client_elevenlabs_requires_mp3_output():
    """Factory should fail fast when ElevenLabs TTS voice ID is missing."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "elevenlabs"
    settings.elevenlabs_api_key = "test-elevenlabs-key"
    settings.elevenlabs_tts_voice_id = None

    with pytest.raises(RunestoneError, match="ElevenLabs voice ID is required for TTS"):
        create_voice_synthesis_client(settings)


def test_create_voice_synthesis_client_elevenlabs_requires_mp3_format():
    """Factory should fail fast when ElevenLabs TTS format is not MP3."""
    settings = Mock(spec=Settings)
    settings.tts_provider = "elevenlabs"
    settings.elevenlabs_api_key = "test-elevenlabs-key"
    settings.elevenlabs_tts_voice_id = "voice-id"
    settings.elevenlabs_tts_model = "eleven_multilingual_v2"
    settings.elevenlabs_tts_output_format = "opus_48000_128"

    with pytest.raises(RunestoneError, match="output format must be an MP3 variant"):
        create_voice_synthesis_client(settings)
