"""
OpenAI-backed voice clients for STT, transcript enhancement, and TTS.
"""

import asyncio
import io
from typing import AsyncIterator

from openai import AsyncOpenAI

from runestone.model_costs.tracking import record_model_interaction


def _transcription_usage(response: object) -> dict[str, object]:
    usage = getattr(response, "usage", None)
    if getattr(usage, "type", None) == "duration":
        return {"second": usage.seconds}
    if getattr(usage, "type", None) == "tokens":
        return {"input_token": usage.input_tokens, "output_token": usage.output_tokens}
    return {}


def _completion_usage(response: object) -> dict[str, object]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return {"input_token": usage.prompt_tokens, "output_token": usage.completion_tokens}


class OpenAISTTClient:
    """OpenAI client for speech-to-text transcription."""

    def __init__(
        self,
        api_key: str,
        transcription_model: str,
    ):
        """
        Initialize OpenAI STT client.

        Args:
            api_key: OpenAI API key
            transcription_model: Model used for speech-to-text
        """
        self._async_client = AsyncOpenAI(api_key=api_key)
        self._transcription_model = transcription_model

    async def transcribe_audio(
        self,
        audio_content: bytes,
        language: str | None = None,
    ) -> str:
        """
        Transcribe raw audio bytes into text.

        Args:
            audio_content: Raw audio bytes from the browser recorder (currently WebM Opus)
            language: Optional ISO-639-1 language code

        Returns:
            Transcribed text or an empty string when provider returns no text
        """
        audio_file = io.BytesIO(audio_content)
        audio_file.name = "recording.webm"

        params = {
            "model": self._transcription_model,
            "file": audio_file,
        }
        if language:
            params["language"] = language

        try:
            response = await self._async_client.audio.transcriptions.create(**params)
        except asyncio.CancelledError:
            record_model_interaction(
                component="voice_stt",
                provider="openai",
                model=self._transcription_model,
                status="cancelled",
            )
            raise
        except Exception:
            record_model_interaction(
                component="voice_stt",
                provider="openai",
                model=self._transcription_model,
                status="failed",
            )
            raise
        record_model_interaction(
            component="voice_stt",
            provider="openai",
            model=self._transcription_model,
            status="completed",
            usage=_transcription_usage(response),
        )
        return (response.text or "").strip()


class OpenAIVoiceEnhancementClient:
    """OpenAI client for transcript cleanup."""

    def __init__(
        self,
        api_key: str,
        enhancement_model: str,
    ):
        """
        Initialize OpenAI transcript enhancement client.

        Args:
            api_key: OpenAI API key
            enhancement_model: Model used for transcript cleanup
        """
        self._async_client = AsyncOpenAI(api_key=api_key)
        self._enhancement_model = enhancement_model

    async def enhance_text(
        self,
        text: str,
        system_prompt: str,
    ) -> str:
        """
        Improve transcript quality using a system prompt.

        Args:
            text: Source text to enhance
            system_prompt: Instruction prompt controlling enhancement behavior

        Returns:
            Enhanced text or an empty string when provider returns no content
        """
        try:
            response = await self._async_client.chat.completions.create(
                model=self._enhancement_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            )
        except asyncio.CancelledError:
            record_model_interaction(
                component="voice_enhancement",
                provider="openai",
                model=self._enhancement_model,
                status="cancelled",
            )
            raise
        except Exception:
            record_model_interaction(
                component="voice_enhancement",
                provider="openai",
                model=self._enhancement_model,
                status="failed",
            )
            raise
        record_model_interaction(
            component="voice_enhancement",
            provider="openai",
            model=self._enhancement_model,
            status="completed",
            usage=_completion_usage(response),
        )
        return (response.choices[0].message.content or "").strip()


class OpenAITTSClient:
    """OpenAI client for streaming text-to-speech synthesis."""

    def __init__(
        self,
        api_key: str,
        tts_model: str,
        tts_voice: str,
    ):
        """
        Initialize OpenAI TTS client.

        Args:
            api_key: OpenAI API key
            tts_model: Model used for speech synthesis
            tts_voice: OpenAI voice identifier
        """
        self._async_client = AsyncOpenAI(api_key=api_key)
        self._tts_model = tts_model
        self._tts_voice = tts_voice

    async def synthesize_speech_stream(
        self,
        text: str,
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """
        Synthesize text and stream MP3 audio chunks.

        Args:
            text: Input text to synthesize
            speed: Playback speed control exposed by the current OpenAI TTS API

        Yields:
            MP3 byte chunks
        """
        status = "failed"
        response = None
        try:
            async with self._async_client.audio.speech.with_streaming_response.create(
                model=self._tts_model,
                voice=self._tts_voice,
                input=text,
                response_format="mp3",
                speed=speed,
            ) as response:
                async for chunk in response.iter_bytes(chunk_size=4096):
                    yield chunk
            status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except GeneratorExit:
            status = "cancelled"
            raise
        except Exception:
            raise
        finally:
            record_model_interaction(
                component="voice_tts",
                provider="openai",
                model=self._tts_model,
                status=status,
                usage={"character": len(text)},
            )
