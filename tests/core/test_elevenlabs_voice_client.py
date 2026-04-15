"""Tests for ElevenLabs STT/TTS clients."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from runestone.core.clients.voice.elevenlabs_voice_client import ElevenLabsSTTClient, ElevenLabsTTSClient


class TestElevenLabsSTTClient:
    """Test cases for ElevenLabs STT client."""

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    def test_instantiation_passes_api_key_to_sdk(self, mock_client_class):
        """STT client should wire the API key into the async SDK."""
        ElevenLabsSTTClient(
            api_key="test-key",
            transcription_model="scribe_v2",
        )
        mock_client_class.assert_called_once_with(api_key="test-key")

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    async def test_transcribe_audio_uses_speech_to_text_convert(self, mock_client_class):
        """Client should send WebM bytes to ElevenLabs Scribe with optional language."""
        mock_client = mock_client_class.return_value
        mock_client.speech_to_text.convert = AsyncMock(return_value=SimpleNamespace(text=" hello "))

        client = ElevenLabsSTTClient(
            api_key="test-key",
            transcription_model="scribe_v2",
        )

        result = await client.transcribe_audio(b"audio-bytes", language="sv")

        assert result == "hello"
        mock_client.speech_to_text.convert.assert_awaited_once()
        call_kwargs = mock_client.speech_to_text.convert.await_args.kwargs
        assert call_kwargs["model_id"] == "scribe_v2"
        assert call_kwargs["language_code"] == "sv"
        filename, audio_file, content_type = call_kwargs["file"]
        assert filename == "recording.webm"
        assert audio_file.name == "recording.webm"
        assert audio_file.getvalue() == b"audio-bytes"
        assert content_type == "audio/webm"

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    async def test_transcribe_audio_omits_language_when_not_provided(self, mock_client_class):
        """Client should let ElevenLabs auto-detect language when none is supplied."""
        mock_client = mock_client_class.return_value
        mock_client.speech_to_text.convert = AsyncMock(return_value=SimpleNamespace(text="hello"))

        client = ElevenLabsSTTClient(
            api_key="test-key",
            transcription_model="scribe_v2",
        )

        result = await client.transcribe_audio(b"audio-bytes")

        assert result == "hello"
        call_kwargs = mock_client.speech_to_text.convert.await_args.kwargs
        assert "language_code" not in call_kwargs

    @patch("runestone.core.clients.voice.elevenlabs_voice_client.AsyncElevenLabs")
    async def test_transcribe_audio_returns_empty_string_for_blank_response(self, mock_client_class):
        """Client should normalize empty provider text to an empty string."""
        mock_client = mock_client_class.return_value
        mock_client.speech_to_text.convert = AsyncMock(return_value=SimpleNamespace(text="   "))

        client = ElevenLabsSTTClient(
            api_key="test-key",
            transcription_model="scribe_v2",
        )

        result = await client.transcribe_audio(b"audio-bytes")

        assert result == ""


class TestElevenLabsTTSClient:
    """Test cases for ElevenLabs TTS client."""

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

        client = ElevenLabsTTSClient(
            api_key="test-key",
            tts_model_id="eleven_multilingual_v2",
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
