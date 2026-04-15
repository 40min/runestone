"""
ElevenLabs-backed voice clients for STT and TTS.
"""

import io
from typing import AsyncIterator

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs


class ElevenLabsSTTClient:
    """ElevenLabs Scribe client for speech-to-text."""

    def __init__(
        self,
        api_key: str,
        transcription_model: str,
    ):
        """
        Initialize the ElevenLabs STT client.

        Args:
            api_key: ElevenLabs API key
            transcription_model: ElevenLabs speech-to-text model identifier
        """
        self._client = AsyncElevenLabs(api_key=api_key)
        self._transcription_model = transcription_model

    async def transcribe_audio(self, audio_content: bytes, language: str | None = None) -> str:
        """
        Transcribe raw audio bytes with ElevenLabs Scribe.

        Args:
            audio_content: Raw audio bytes from the browser recorder
            language: Optional ISO-639-1 language code

        Returns:
            Transcribed text or an empty string when provider returns no text
        """
        audio_file = io.BytesIO(audio_content)
        audio_file.name = "recording.webm"

        params = {
            "model_id": self._transcription_model,
            "file": ("recording.webm", audio_file, "audio/webm"),
        }
        if language:
            params["language_code"] = language

        response = await self._client.speech_to_text.convert(**params)
        return (getattr(response, "text", None) or "").strip()


class ElevenLabsTTSClient:
    """ElevenLabs client for streaming text-to-speech synthesis."""

    def __init__(
        self,
        api_key: str,
        tts_model_id: str,
        voice_id: str,
        output_format: str,
        stability: float,
        similarity_boost: float,
        style: float,
        use_speaker_boost: bool,
    ):
        """
        Initialize the ElevenLabs TTS client.

        Args:
            api_key: ElevenLabs API key
            tts_model_id: ElevenLabs text-to-speech model identifier
            voice_id: ElevenLabs voice identifier
            output_format: Requested audio format for generated speech
            stability: ElevenLabs stability tuning
            similarity_boost: ElevenLabs similarity boost tuning
            style: ElevenLabs style tuning
            use_speaker_boost: Whether to enable speaker boost
        """
        self._client = AsyncElevenLabs(api_key=api_key)
        self._tts_model_id = tts_model_id
        self._voice_id = voice_id
        self._output_format = output_format
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._use_speaker_boost = use_speaker_boost

    def _build_voice_settings(self, speed: float) -> VoiceSettings:
        """
        Build per-request voice settings.

        The existing UI already passes a speed control through chat/TTS flows,
        so we forward it here to preserve behavior across providers.
        """
        return VoiceSettings(
            stability=self._stability,
            similarity_boost=self._similarity_boost,
            style=self._style,
            use_speaker_boost=self._use_speaker_boost,
            speed=speed,
        )

    async def synthesize_speech_stream(self, text: str, speed: float = 1.0) -> AsyncIterator[bytes]:
        """
        Synthesize text and stream MP3 audio chunks.

        Args:
            text: Input text to synthesize
            speed: Speech speed forwarded to ElevenLabs voice settings

        Yields:
            MP3 byte chunks
        """
        voice_settings = self._build_voice_settings(speed=speed)
        async for chunk in self._client.text_to_speech.stream(
            voice_id=self._voice_id,
            text=text,
            model_id=self._tts_model_id,
            output_format=self._output_format,
            voice_settings=voice_settings,
        ):
            yield chunk
