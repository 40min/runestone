"""
Factory helpers and contracts for voice provider clients.
"""

from typing import AsyncIterator, Protocol

from runestone.config import Settings
from runestone.core.clients.voice.elevenlabs_voice_client import ElevenLabsSTTClient, ElevenLabsTTSClient
from runestone.core.clients.voice.openai_voice_client import (
    OpenAISTTClient,
    OpenAITTSClient,
    OpenAIVoiceEnhancementClient,
)
from runestone.core.exceptions import APIKeyError, RunestoneError


class VoiceTranscriptionClient(Protocol):
    """Contract for speech-to-text providers."""

    async def transcribe_audio(self, audio_content: bytes, language: str | None = None) -> str:
        """Transcribe raw audio bytes to text."""


class VoiceEnhancementClient(Protocol):
    """Contract for transcript cleanup providers."""

    async def enhance_text(self, text: str, system_prompt: str) -> str:
        """Enhance transcript text with provider-specific language model support."""


class VoiceSynthesisClient(Protocol):
    """Contract for text-to-speech providers."""

    async def synthesize_speech_stream(self, text: str, speed: float = 1.0) -> AsyncIterator[bytes]:
        """Yield synthesized audio bytes for the input text."""


def _require_value(value: str | None, message: str) -> str:
    """Return a non-empty config value or raise a setup error."""
    if value is None or not str(value).strip():
        raise RunestoneError(message)
    return str(value).strip()


def _validate_openai_api_key(settings: Settings) -> str:
    """Validate OpenAI API key for voice operations."""
    api_key = settings.openai_api_key
    if not api_key or not api_key.strip():
        raise APIKeyError("OpenAI API key is required for voice features. Set OPENAI_API_KEY.")
    return api_key


def _validate_elevenlabs_api_key(settings: Settings) -> str:
    """Validate ElevenLabs API key for voice operations."""
    api_key = settings.elevenlabs_api_key
    if not api_key or not api_key.strip():
        raise APIKeyError("ElevenLabs API key is required for voice features. Set ELEVENLABS_API_KEY.")
    return api_key


def _create_openai_stt_client(settings: Settings) -> OpenAISTTClient:
    """Create OpenAI STT client from validated config."""
    api_key = _validate_openai_api_key(settings)
    transcription_model = _require_value(
        settings.voice_transcription_model,
        "VOICE_TRANSCRIPTION_MODEL is required when VOICE_TRANSCRIPTION_PROVIDER=openai.",
    )
    return OpenAISTTClient(
        api_key=api_key,
        transcription_model=transcription_model,
    )


def _create_openai_enhancement_client(settings: Settings) -> OpenAIVoiceEnhancementClient:
    """Create OpenAI transcript enhancement client from validated config."""
    api_key = _validate_openai_api_key(settings)
    enhancement_model = _require_value(
        settings.voice_enhancement_model,
        "VOICE_ENHANCEMENT_MODEL is required for transcript cleanup.",
    )
    return OpenAIVoiceEnhancementClient(
        api_key=api_key,
        enhancement_model=enhancement_model,
    )


def _create_openai_tts_client(settings: Settings) -> OpenAITTSClient:
    """Create OpenAI TTS client from validated config."""
    api_key = _validate_openai_api_key(settings)
    tts_model = _require_value(settings.tts_model, "TTS_MODEL is required when TTS_PROVIDER=openai.")
    tts_voice = _require_value(settings.tts_voice, "TTS_VOICE is required when TTS_PROVIDER=openai.")
    return OpenAITTSClient(
        api_key=api_key,
        tts_model=tts_model,
        tts_voice=tts_voice,
    )


def _create_elevenlabs_stt_client(settings: Settings) -> ElevenLabsSTTClient:
    """Create ElevenLabs STT client from validated config."""
    api_key = _validate_elevenlabs_api_key(settings)
    transcription_model = _require_value(
        settings.voice_transcription_model,
        "VOICE_TRANSCRIPTION_MODEL is required when VOICE_TRANSCRIPTION_PROVIDER=elevenlabs.",
    )
    return ElevenLabsSTTClient(
        api_key=api_key,
        transcription_model=transcription_model,
    )


def _create_elevenlabs_tts_client(settings: Settings) -> ElevenLabsTTSClient:
    """Create ElevenLabs TTS client from validated config."""
    api_key = _validate_elevenlabs_api_key(settings)
    voice_id = _require_value(
        settings.elevenlabs_tts_voice_id,
        "ElevenLabs voice ID is required for TTS. Set ELEVENLABS_TTS_VOICE_ID when TTS_PROVIDER=elevenlabs.",
    )
    model_id = _require_value(
        settings.elevenlabs_tts_model,
        "ELEVENLABS_TTS_MODEL is required when TTS_PROVIDER=elevenlabs.",
    )
    output_format = _require_value(
        settings.elevenlabs_tts_output_format,
        "ELEVENLABS_TTS_OUTPUT_FORMAT is required when TTS_PROVIDER=elevenlabs.",
    )
    if not output_format.startswith("mp3_"):
        raise RunestoneError(
            "ElevenLabs TTS output format must be an MP3 variant for browser playback. "
            "Set ELEVENLABS_TTS_OUTPUT_FORMAT to an mp3_* value."
        )
    return ElevenLabsTTSClient(
        api_key=api_key,
        tts_model_id=model_id,
        voice_id=voice_id,
        output_format=output_format,
        stability=settings.elevenlabs_tts_stability,
        similarity_boost=settings.elevenlabs_tts_similarity_boost,
        style=settings.elevenlabs_tts_style,
        use_speaker_boost=settings.elevenlabs_tts_use_speaker_boost,
    )


def create_voice_transcription_client(settings: Settings) -> VoiceTranscriptionClient:
    """
    Create the configured transcription client.

    Transcription and TTS are selected independently so rollout can happen in phases.
    """
    provider = settings.voice_transcription_provider.lower()
    if provider == "openai":
        return _create_openai_stt_client(settings)
    if provider == "elevenlabs":
        return _create_elevenlabs_stt_client(settings)
    raise RunestoneError(f"Unsupported voice transcription provider: {provider}")


def create_voice_enhancement_client(settings: Settings) -> VoiceEnhancementClient:
    """Create the transcript cleanup client used after any STT provider."""
    return _create_openai_enhancement_client(settings)


def create_voice_synthesis_client(settings: Settings) -> VoiceSynthesisClient:
    """
    Create the configured text-to-speech client.

    ElevenLabs integration will be added in the next migration phase.
    """
    provider = settings.tts_provider.lower()
    if provider == "openai":
        return _create_openai_tts_client(settings)
    if provider == "elevenlabs":
        return _create_elevenlabs_tts_client(settings)
    raise RunestoneError(f"Unsupported TTS provider: {provider}")
