"""Tests for OpenAI voice capability clients."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.core.clients.voice.openai_voice_client import (
    OpenAISTTClient,
    OpenAITTSClient,
    OpenAIVoiceEnhancementClient,
)


@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
def test_stt_instantiation_wires_api_key(mock_async_openai):
    """STT client should pass API key into OpenAI async SDK."""
    OpenAISTTClient(
        api_key="test-key",
        transcription_model="whisper-1",
    )
    mock_async_openai.assert_called_once_with(api_key="test-key")


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_transcribe_audio_uses_async_client(mock_async_openai, caplog):
    """Transcription should call the async OpenAI client."""
    mock_client = mock_async_openai.return_value
    mock_client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(text=" hello "))

    client = OpenAISTTClient(
        api_key="test-key",
        transcription_model="whisper-1",
    )

    with caplog.at_level(logging.WARNING, logger="runestone.model_costs.tracking"):
        result = await client.transcribe_audio(b"audio-bytes", language="sv")

    assert result == "hello"
    mock_client.audio.transcriptions.create.assert_awaited_once()
    call_kwargs = mock_client.audio.transcriptions.create.await_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["language"] == "sv"
    assert call_kwargs["file"].name == "recording.webm"
    assert "interaction ignored without active operation" in caplog.text


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_transcription_records_duration_usage(mock_async_openai):
    """Provider STT usage should produce content-free estimated accounting."""
    response = SimpleNamespace(text="secret transcript", usage=SimpleNamespace(type="duration", seconds=2.5))
    mock_async_openai.return_value.audio.transcriptions.create = AsyncMock(return_value=response)
    client = OpenAISTTClient(api_key="test-key", transcription_model="whisper-1")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        await client.transcribe_audio(b"private audio")

    record.assert_called_once_with(
        component="voice_stt",
        provider="openai",
        model="whisper-1",
        status="completed",
        usage={"second": 2.5},
    )


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_transcription_records_token_usage(mock_async_openai):
    response = SimpleNamespace(
        text="secret transcript",
        usage=SimpleNamespace(type="tokens", input_tokens=12, output_tokens=3),
    )
    mock_async_openai.return_value.audio.transcriptions.create = AsyncMock(return_value=response)
    client = OpenAISTTClient(api_key="test-key", transcription_model="gpt-4o-transcribe")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        await client.transcribe_audio(b"private audio")

    assert record.call_args.kwargs["usage"] == {"input_token": 12, "output_token": 3}


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
def test_enhancement_instantiation_wires_api_key(mock_async_openai):
    """Enhancement client should pass API key into OpenAI async SDK."""
    OpenAIVoiceEnhancementClient(
        api_key="test-key",
        enhancement_model="gpt-4o-mini",
    )
    mock_async_openai.assert_called_once_with(api_key="test-key")


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_enhancement_client_uses_async_chat_client(mock_async_openai):
    """Enhancement should call the async OpenAI chat client."""
    mock_client = mock_async_openai.return_value
    mock_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" enhanced text "))])
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    client = OpenAIVoiceEnhancementClient(
        api_key="test-key",
        enhancement_model="gpt-4o-mini",
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


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_enhancement_records_token_usage(mock_async_openai):
    """Transcript enhancement should record token quantities without its text."""
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="enhanced"))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
    )
    mock_async_openai.return_value.chat.completions.create = AsyncMock(return_value=response)
    client = OpenAIVoiceEnhancementClient(api_key="test-key", enhancement_model="gpt-4o-mini")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        await client.enhance_text("private source", "private instruction")

    assert record.call_args.kwargs["usage"] == {"input_token": 10, "output_token": 4}


@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
def test_tts_instantiation_wires_api_key(mock_async_openai):
    """TTS client should pass API key into OpenAI async SDK."""
    OpenAITTSClient(
        api_key="test-key",
        tts_model="gpt-4o-mini-tts",
        tts_voice="alloy",
    )
    mock_async_openai.assert_called_once_with(api_key="test-key")


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_tts_records_completed_attempt_once(mock_async_openai):
    """A fully consumed stream should record one completed paid attempt."""
    response = MagicMock()

    async def chunks(chunk_size):
        assert chunk_size == 4096
        yield b"audio"

    response.iter_bytes = chunks
    context = AsyncMock()
    context.__aenter__.return_value = response
    mock_async_openai.return_value.audio.speech.with_streaming_response.create.return_value = context
    client = OpenAITTSClient(api_key="test-key", tts_model="tts-1", tts_voice="alloy")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        assert [chunk async for chunk in client.synthesize_speech_stream("Hello")] == [b"audio"]

    assert record.call_count == 1
    assert record.call_args.kwargs["status"] == "completed"
    assert record.call_args.kwargs["usage"] == {"character": 5}


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_failed_transcription_records_unknown_cost(mock_async_openai):
    """A failed potentially billed request should remain attributed with unknown cost."""
    mock_async_openai.return_value.audio.transcriptions.create = AsyncMock(side_effect=RuntimeError("provider failed"))
    client = OpenAISTTClient(api_key="test-key", transcription_model="whisper-1")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        with pytest.raises(RuntimeError, match="provider failed"):
            await client.transcribe_audio(b"private audio")

    assert record.call_args.kwargs["status"] == "failed"


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_tts_early_close_records_cancelled_attempt_once(mock_async_openai):
    """Abandoning a submitted stream must not be reported as a successful zero-use call."""
    response = MagicMock()

    async def chunks(chunk_size):
        yield b"first"
        yield b"second"

    response.iter_bytes = chunks
    context = AsyncMock()
    context.__aenter__.return_value = response
    mock_async_openai.return_value.audio.speech.with_streaming_response.create.return_value = context
    client = OpenAITTSClient(api_key="test-key", tts_model="tts-1", tts_voice="alloy")
    stream = client.synthesize_speech_stream("private text")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        assert await anext(stream) == b"first"
        await stream.aclose()

    record.assert_called_once()
    assert record.call_args.kwargs["status"] == "cancelled"
    assert record.call_args.kwargs["usage"] == {"character": 12}


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_tts_provider_failure_records_attempt_once(mock_async_openai):
    """A failed submitted stream should retain its known input usage."""
    context = AsyncMock()
    context.__aenter__.side_effect = RuntimeError("provider failed")
    mock_async_openai.return_value.audio.speech.with_streaming_response.create.return_value = context
    client = OpenAITTSClient(api_key="test-key", tts_model="tts-1", tts_voice="alloy")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        with pytest.raises(RuntimeError, match="provider failed"):
            async for _ in client.synthesize_speech_stream("private text"):
                pass

    record.assert_called_once()
    assert record.call_args.kwargs["status"] == "failed"
    assert record.call_args.kwargs["usage"] == {"character": 12}


@pytest.mark.anyio
@patch("runestone.core.clients.voice.openai_voice_client.AsyncOpenAI")
async def test_tts_cancellation_records_attempt_once(mock_async_openai):
    """Task cancellation should be recorded once and propagated."""
    response = MagicMock()

    async def chunks(chunk_size):
        raise asyncio.CancelledError
        yield  # pragma: no cover

    response.iter_bytes = chunks
    context = AsyncMock()
    context.__aenter__.return_value = response
    mock_async_openai.return_value.audio.speech.with_streaming_response.create.return_value = context
    client = OpenAITTSClient(api_key="test-key", tts_model="tts-1", tts_voice="alloy")

    with patch("runestone.core.clients.voice.openai_voice_client.record_model_interaction") as record:
        with pytest.raises(asyncio.CancelledError):
            async for _ in client.synthesize_speech_stream("Hello"):
                pass

    record.assert_called_once()
    assert record.call_args.kwargs["status"] == "cancelled"
