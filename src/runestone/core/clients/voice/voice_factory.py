"""
Factory helpers and contracts for voice provider clients.
"""

from typing import AsyncIterator, Protocol

from runestone.config import Settings
from runestone.core.clients.voice.openai_voice_client import OpenAIVoiceClient
from runestone.core.exceptions import RunestoneError


class VoiceTranscriptionClient(Protocol):
    """Contract for speech-to-text and transcript cleanup providers."""

    async def transcribe_audio(self, audio_content: bytes, language: str | None = None) -> str:
        """Transcribe raw audio bytes to text."""

    async def enhance_text(self, text: str, system_prompt: str) -> str:
        """Enhance transcript text with provider-specific language model support."""


class VoiceSynthesisClient(Protocol):
    """Contract for text-to-speech providers."""

    async def synthesize_speech_stream(self, text: str, speed: float = 1.0) -> AsyncIterator[bytes]:
        """Yield synthesized audio bytes for the input text."""


def _create_openai_voice_client(settings: Settings) -> OpenAIVoiceClient:
    """Create the OpenAI voice client using current app settings."""
    return OpenAIVoiceClient(
        api_key=settings.openai_api_key,
        transcription_model=settings.voice_transcription_model,
        enhancement_model=settings.voice_enhancement_model,
        tts_model=settings.tts_model,
        tts_voice=settings.tts_voice,
    )


def create_voice_transcription_client(settings: Settings) -> VoiceTranscriptionClient:
    """
    Create the configured transcription client.

    Transcription and TTS are selected independently so rollout can happen in phases.
    """
    provider = settings.voice_transcription_provider.lower()
    if provider == "openai":
        return _create_openai_voice_client(settings)
    if provider == "elevenlabs":
        raise RunestoneError(
            "VOICE_TRANSCRIPTION_PROVIDER=elevenlabs is not implemented yet. "
            "Use VOICE_TRANSCRIPTION_PROVIDER=openai for now."
        )
    raise RunestoneError(f"Unsupported voice transcription provider: {provider}")


def create_voice_synthesis_client(settings: Settings) -> VoiceSynthesisClient:
    """
    Create the configured text-to-speech client.

    ElevenLabs integration will be added in the next migration phase.
    """
    provider = settings.tts_provider.lower()
    if provider == "openai":
        return _create_openai_voice_client(settings)
    if provider == "elevenlabs":
        raise RunestoneError("TTS_PROVIDER=elevenlabs is not implemented yet. Use TTS_PROVIDER=openai for now.")
    raise RunestoneError(f"Unsupported TTS provider: {provider}")
