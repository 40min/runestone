"""Tests for the ElevenLabs voice client."""

from unittest.mock import MagicMock, patch

import pytest

from runestone.core.clients.voice.elevenlabs_voice_client import ElevenLabsVoiceClient
from runestone.core.exceptions import APIKeyError, RunestoneError


class TestElevenLabsVoiceClient:
    """Test cases for ElevenLabsVoiceClient."""

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    def test_instantiation_requires_api_key(self, mock_client_class):
        """Client should reject missing API key."""
        with pytest.raises(APIKeyError, match="ElevenLabs API key is required"):
            ElevenLabsVoiceClient(
                api_key="",
                model_id="eleven_multilingual_v2",
                voice_id="voice-id",
                output_format="mp3_44100_128",
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            )

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    def test_instantiation_requires_voice_id(self, mock_client_class):
        """Client should reject missing voice ID for TTS."""
        with pytest.raises(RunestoneError, match="ElevenLabs voice ID is required for TTS"):
            ElevenLabsVoiceClient(
                api_key="test-key",
                model_id="eleven_multilingual_v2",
                voice_id="",
                output_format="mp3_44100_128",
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            )

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    def test_instantiation_rejects_non_mp3_output_format(self, mock_client_class):
        """Client should fail fast on formats the browser playback path cannot decode."""
        with pytest.raises(RunestoneError, match="output format must be an MP3 variant"):
            ElevenLabsVoiceClient(
                api_key="test-key",
                model_id="eleven_multilingual_v2",
                voice_id="voice-id",
                output_format="opus_48000_128",
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            )

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.VoiceSettings")
    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    async def test_synthesize_speech_stream(self, mock_client_class, mock_voice_settings):
        """Client should stream raw bytes from ElevenLabs SDK."""
        mock_client = mock_client_class.return_value

        async def stream_audio(**kwargs):
            yield b"chunk1"
            yield b"chunk2"

        mock_client.text_to_speech.stream = MagicMock(side_effect=stream_audio)
        mock_voice_settings.return_value = "voice-settings"

        client = ElevenLabsVoiceClient(
            api_key="test-key",
            model_id="eleven_multilingual_v2",
            voice_id="voice-id",
            output_format="mp3_44100_128",
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True,
        )

        chunks = []
        async for chunk in client.synthesize_speech_stream("Hello", speed=1.25):
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]
        mock_voice_settings.assert_called_once_with(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True,
            speed=1.25,
        )
        mock_client.text_to_speech.stream.assert_called_once_with(
            voice_id="voice-id",
            text="Hello",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings="voice-settings",
        )
