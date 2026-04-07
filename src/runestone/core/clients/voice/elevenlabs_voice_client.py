"""
ElevenLabs-backed voice client for text-to-speech synthesis.
"""

from typing import AsyncIterator

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs

from runestone.core.exceptions import APIKeyError, RunestoneError


class ElevenLabsVoiceClient:
    """Voice client that wraps ElevenLabs TTS streaming for Runestone."""

    def __init__(
        self,
        api_key: str,
        model_id: str,
        voice_id: str,
        output_format: str,
        stability: float,
        similarity_boost: float,
        style: float,
        use_speaker_boost: bool,
    ):
        """
        Initialize the ElevenLabs voice client.

        Args:
            api_key: ElevenLabs API key
            model_id: ElevenLabs model identifier
            voice_id: ElevenLabs voice identifier
            output_format: Requested audio format for generated speech
            stability: ElevenLabs stability tuning
            similarity_boost: ElevenLabs similarity boost tuning
            style: ElevenLabs style tuning
            use_speaker_boost: Whether to enable speaker boost
        """
        if not api_key:
            raise APIKeyError("ElevenLabs API key is required for voice features. Set ELEVENLABS_API_KEY.")
        if not voice_id:
            raise RunestoneError(
                "ElevenLabs voice ID is required for TTS. Set ELEVENLABS_TTS_VOICE_ID when TTS_PROVIDER=elevenlabs."
            )
        if not output_format.startswith("mp3_"):
            raise RunestoneError(
                "ElevenLabs TTS output format must be an MP3 variant for browser playback. "
                "Set ELEVENLABS_TTS_OUTPUT_FORMAT to an mp3_* value."
            )

        self._client = AsyncElevenLabs(api_key=api_key)
        self._model_id = model_id
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
            model_id=self._model_id,
            output_format=self._output_format,
            voice_settings=voice_settings,
        ):
            yield chunk
