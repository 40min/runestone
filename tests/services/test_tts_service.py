import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.model_costs.tracking import _CostCollector, record_model_interaction
from runestone.services.tts_service import TTSService


def _tracking_session(activity: str) -> _CostCollector:
    return _CostCollector(activity)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.openai_api_key = "fake-key"
    mock.tts_model = "gpt-4o-mini-tts"
    mock.tts_voice = "onyx"
    return mock


@pytest.fixture
def mock_synthesis_client():
    """Create a mock synthesis client."""
    client = MagicMock()

    async def stream_chunks(
        text: str,
        speed: float = 1.0,
    ):
        for chunk in [b"chunk1", b"chunk2"]:
            yield chunk

    client.synthesize_speech_stream = MagicMock(side_effect=stream_chunks)
    return client


def _make_tts_child():
    return _tracking_session("chat_turn").transfer("tts")


@pytest.mark.anyio
async def test_synthesize_speech_stream(mock_settings, mock_synthesis_client):
    """Test streaming speech synthesis."""
    service = TTSService(mock_settings, mock_synthesis_client)
    chunks = []
    async for chunk in service.synthesize_speech_stream("Hello"):
        chunks.append(chunk)

    assert chunks == [b"chunk1", b"chunk2"]
    mock_synthesis_client.synthesize_speech_stream.assert_called_once_with(
        text="Hello",
        speed=1.0,
    )


@pytest.mark.anyio
async def test_push_audio_to_client_no_connection(mock_settings, mock_synthesis_client):
    """Test pushing audio when no WebSocket connection exists."""
    service = TTSService(mock_settings, mock_synthesis_client)

    # Should return silently if user_id not in connection_manager
    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=None):
        await service.push_audio_to_client(user_id=1, text="Hello", cost_tracking=_make_tts_child())


@pytest.mark.anyio
async def test_no_connection_closes_tts_child_as_neutral_skip(mock_settings, mock_synthesis_client):
    service = TTSService(mock_settings, mock_synthesis_client)
    operation = _tracking_session("chat_turn")
    child = operation.transfer("tts")
    operation.emit_preliminary()

    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=None):
        await service.push_audio_to_client(user_id=1, text="Hello", cost_tracking=child)
        await service._active_tasks[1]

    assert child.status == "skipped_no_websocket"
    assert operation.state == "corrected_emitted"
    assert operation.interactions == ()


@pytest.mark.anyio
async def test_stream_audio_task_success(mock_settings, mock_synthesis_client):
    """Test successful audio push via WebSocket using internal task."""

    async def stream_one_chunk(text: str, speed: float = 1.0, **_kwargs):
        yield b"chunk1"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=stream_one_chunk)

    service = TTSService(mock_settings, mock_synthesis_client)

    # Mock WebSocket
    mock_ws = MagicMock()
    mock_ws.send_bytes = AsyncMock()
    mock_ws.send_json = AsyncMock()

    # patch connection_manager
    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=mock_ws):
        await service._stream_audio_task(user_id=1, text="Hello", cost_tracking=_make_tts_child())

    # Verify chunks sent
    assert mock_ws.send_bytes.await_count == 1
    mock_ws.send_bytes.assert_awaited_with(b"chunk1")
    assert mock_ws.send_json.await_count == 1
    mock_ws.send_json.assert_awaited_with({"status": "complete"})


@pytest.mark.anyio
async def test_stream_audio_task_records_direct_tts_in_parent_background(
    mock_settings,
    mock_synthesis_client,
    caplog,
):
    async def stream_one_chunk(
        text: str,
        speed: float = 1.0,
    ):
        record_model_interaction(
            component="voice_tts",
            provider="openai",
            model="gpt-4o-mini-tts",
            status="completed",
            usage={"character": len(text)},
            provider_cost_usd="0.04",
        )
        yield b"chunk1"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=stream_one_chunk)
    service = TTSService(mock_settings, mock_synthesis_client)
    operation = _tracking_session("chat_turn")
    child = operation.transfer("tts")
    operation.emit_preliminary()
    websocket = MagicMock(send_bytes=AsyncMock(), send_json=AsyncMock())

    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=websocket):
        with caplog.at_level("INFO", logger="runestone.model_costs.tracking"):
            await service._stream_audio_task(1, "Hello", cost_tracking=child)

    assert child.status == "completed"
    assert [(record.phase, record.component) for record in operation.interactions] == [("background", "voice_tts")]
    mock_synthesis_client.synthesize_speech_stream.assert_called_once_with(text="Hello", speed=1.0)
    corrected = [
        record.message for record in caplog.records if record.message.startswith("model_cost stage=corrected ")
    ]
    assert len(corrected) == 1
    assert "known_total_usd=0.04" in corrected[0]


@pytest.mark.anyio
async def test_stream_audio_failure_closes_tts_child(mock_settings, mock_synthesis_client):
    async def fail_stream(text: str, speed: float = 1.0, **_kwargs):
        del text
        del speed
        raise RuntimeError("provider failed")
        yield b"unreachable"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=fail_stream)
    service = TTSService(mock_settings, mock_synthesis_client)
    operation = _tracking_session("chat_turn")
    child = operation.transfer("tts")
    websocket = MagicMock(send_bytes=AsyncMock(), send_json=AsyncMock())

    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=websocket):
        with pytest.raises(RuntimeError, match="provider failed"):
            await service._stream_audio_task(1, "Hello", cost_tracking=child)

    assert child.status == "failed"


@pytest.mark.anyio
async def test_stream_audio_cancellation_closes_tts_child(mock_settings, mock_synthesis_client):
    started = asyncio.Event()

    async def slow_stream(text: str, speed: float = 1.0, **_kwargs):
        del text
        del speed
        started.set()
        await asyncio.sleep(60)
        yield b"unreachable"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=slow_stream)
    service = TTSService(mock_settings, mock_synthesis_client)
    operation = _tracking_session("chat_turn")
    child = operation.transfer("tts")
    websocket = MagicMock(send_bytes=AsyncMock(), send_json=AsyncMock())

    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=websocket):
        task = asyncio.create_task(service._stream_audio_task(1, "Hello", cost_tracking=child))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert child.status == "cancelled"


@pytest.mark.anyio
async def test_push_audio_to_client_manages_task(mock_settings, mock_synthesis_client):
    """Test that push_audio_to_client creates a task."""
    service = TTSService(mock_settings, mock_synthesis_client)
    service._stream_audio_task = AsyncMock()

    cost_tracking = _make_tts_child()
    await service.push_audio_to_client(user_id=1, text="Hello", cost_tracking=cost_tracking)

    # Check that a task was created and stored
    assert 1 in service._active_tasks
    task = service._active_tasks[1]
    assert isinstance(task, asyncio.Task)
    await task  # Wait for it to finish
    service._stream_audio_task.assert_awaited_once_with(1, "Hello", cost_tracking, 1.0)


@pytest.mark.anyio
async def test_push_audio_cancels_previous_task(mock_settings, mock_synthesis_client):
    """Test that new requests cancel previous ones."""
    service = TTSService(mock_settings, mock_synthesis_client)

    # Create a slow task that we can spy on
    async def slow_task(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Need to re-raise for task.cancelled() to be true
            raise

    service._stream_audio_task = AsyncMock(side_effect=slow_task)

    # Start first task
    await service.push_audio_to_client(user_id=1, text="First", cost_tracking=_make_tts_child())
    task1 = service._active_tasks[1]

    # Start second task - this should await the cancellation of task1
    # To test this, we'll run it in a separate task and see it wait
    push_task = asyncio.create_task(
        service.push_audio_to_client(user_id=1, text="Second", cost_tracking=_make_tts_child())
    )

    # Yield to allow task1 to be cancelled
    await asyncio.sleep(0.1)

    assert task1.cancelled()

    # Cleanup
    push_task.cancel()
    if 1 in service._active_tasks:
        service._active_tasks[1].cancel()


@pytest.mark.anyio
async def test_push_audio_replacement_records_provider_cancellation_before_child_close(
    mock_settings,
    mock_synthesis_client,
):
    service = TTSService(mock_settings, mock_synthesis_client)
    first_started = asyncio.Event()
    calls = 0

    async def stream(
        text: str,
        speed: float = 1.0,
    ):
        nonlocal calls
        del speed
        calls += 1
        if calls == 1:
            first_started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                record_model_interaction(
                    component="voice_tts",
                    provider="openai",
                    model="tts-model",
                    status="cancelled",
                    usage={"character": len(text)},
                )
                raise
        yield b"audio"

    mock_synthesis_client.synthesize_speech_stream = MagicMock(side_effect=stream)
    previous_operation = _tracking_session("chat_turn")
    previous_child = previous_operation.transfer("tts")
    previous_operation.emit_preliminary()
    next_operation = _tracking_session("chat_turn")
    next_child = next_operation.transfer("tts")
    websocket = MagicMock(send_bytes=AsyncMock(), send_json=AsyncMock())

    with patch("runestone.services.tts_service.connection_manager.get_connection", return_value=websocket):
        await service.push_audio_to_client(1, "First", cost_tracking=previous_child)
        previous_task = service._active_tasks[1]
        await first_started.wait()
        await service.push_audio_to_client(1, "Second", cost_tracking=next_child)
        await service._active_tasks[1]

    assert previous_task.cancelled()
    assert previous_child.status == "stale_replaced"
    assert previous_operation.state == "corrected_emitted"
    assert len(previous_operation.interactions) == 1
    assert previous_operation.interactions[0].status == "cancelled"
    assert previous_operation.interactions[0].cost_quality == "unknown"
    assert next_child.status == "completed"


@pytest.mark.anyio
async def test_push_audio_replacement_seals_cancellation_resistant_task_as_unknown(
    mock_settings,
    mock_synthesis_client,
    caplog,
):
    service = TTSService(mock_settings, mock_synthesis_client)
    service.CANCELLATION_GRACE_SECONDS = 0.01
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def resistant_task(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            return
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await release.wait()

    service._stream_audio_task = AsyncMock(side_effect=resistant_task)
    previous_operation = _tracking_session("chat_turn")
    previous_child = previous_operation.transfer("tts")
    previous_operation.emit_preliminary()
    next_operation = _tracking_session("chat_turn")
    next_child = next_operation.transfer("tts")

    await service.push_audio_to_client(1, "First", cost_tracking=previous_child)
    previous_task = service._active_tasks[1]
    await started.wait()
    with caplog.at_level("INFO", logger="runestone.model_costs.tracking"):
        await service.push_audio_to_client(1, "Second", cost_tracking=next_child)

    assert not previous_task.done()
    assert previous_child.status == "cancelled_with_unknown_usage"
    assert previous_operation.state == "corrected_emitted"
    assert previous_operation.interactions == ()
    corrected = [record.message for record in caplog.records if "stage=corrected" in record.message]
    assert len(corrected) == 1
    assert "cost_quality=unknown" in corrected[0]
    assert "unknown_calls=1" in corrected[0]

    release.set()
    await previous_task


@pytest.mark.anyio
async def test_cancelled_replacement_scheduling_seals_both_children_and_corrects_once(
    mock_settings,
    mock_synthesis_client,
    caplog,
):
    service = TTSService(mock_settings, mock_synthesis_client)
    service.CANCELLATION_GRACE_SECONDS = 1.0
    old_started = asyncio.Event()
    release_old = asyncio.Event()
    calls = 0

    async def resistant_task(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            return
        old_started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await release_old.wait()

    service._stream_audio_task = AsyncMock(side_effect=resistant_task)
    old_operation = _tracking_session("chat_turn")
    old_child = old_operation.transfer("tts")
    old_operation.emit_preliminary()
    new_operation = _tracking_session("chat_turn")
    cost_tracking = new_operation.transfer("post_turn")
    fresh_tts_child = new_operation.transfer("tts")
    new_operation.emit_preliminary()

    await service.push_audio_to_client(1, "First", cost_tracking=old_child)
    old_task = service._active_tasks[1]
    await old_started.wait()

    with caplog.at_level("INFO", logger="runestone.model_costs.tracking"):
        scheduling = asyncio.create_task(service.push_audio_to_client(1, "Replacement", cost_tracking=fresh_tts_child))
        await asyncio.sleep(0)
        scheduling.cancel()
        with pytest.raises(asyncio.CancelledError):
            await scheduling

        assert old_child.status == "cancelled_with_unknown_usage"
        assert old_operation.state == "corrected_emitted"
        assert fresh_tts_child.status == "cancelled"
        assert cost_tracking.status is None
        assert new_operation.state == "preliminary_emitted"
        cost_tracking.finish("completed")

    assert not old_task.done()
    assert new_operation.state == "corrected_emitted"
    old_corrected = [
        record.message
        for record in caplog.records
        if "stage=corrected" in record.message and f"operation_id={old_operation.operation_id}" in record.message
    ]
    assert len(old_corrected) == 1
    assert "cost_quality=unknown" in old_corrected[0]
    assert "unknown_calls=1" in old_corrected[0]
    new_corrected = [
        record.message
        for record in caplog.records
        if "stage=corrected" in record.message and f"operation_id={new_operation.operation_id}" in record.message
    ]
    assert len(new_corrected) == 1
    assert "post_turn_status=completed" in new_corrected[0]
    assert "tts_status=cancelled" in new_corrected[0]

    assert old_child.finish("stale_replaced") is False
    release_old.set()
    await old_task
