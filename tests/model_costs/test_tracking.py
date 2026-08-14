import asyncio
import logging
from decimal import Decimal

import pytest

from runestone.model_costs.pricing import ModelPrice, PriceSnapshot
from runestone.model_costs.tracking import (
    CostTrackingHandle,
    aggregate_quality,
    calculate_cost,
    record_model_interaction,
    suspend_model_cost_tracking,
    track_model_costs,
    track_model_costs_with_background,
)


@pytest.fixture
def snapshot() -> PriceSnapshot:
    return PriceSnapshot(
        fetched_at="2026-08-11T12:00:00Z",
        models={
            "openai/gpt-test": ModelPrice(
                source="models.dev",
                source_url="https://models.dev/api.json",
                source_model_id="gpt-test",
                last_successful_at="2026-08-11T12:00:00Z",
                stale=False,
                rates_usd={
                    "cached_input_write_token": Decimal("0.0004"),
                    "input_token": Decimal("0.001"),
                    "output_token": Decimal("0.002"),
                },
            )
        },
    )


@pytest.fixture(autouse=True)
def use_snapshot(snapshot: PriceSnapshot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("runestone.model_costs.tracking.load_price_snapshot", lambda path: snapshot)


def test_cost_accounting_invariants(snapshot: PriceSnapshot) -> None:
    exact = calculate_cost("openai", "gpt-test", {"input_token": 10}, provider_cost_usd="0.75", snapshot=snapshot)
    estimated = calculate_cost("openai", "gpt-test", {"input_token": 10, "output_token": 2}, snapshot=snapshot)
    partial = calculate_cost("openai", "gpt-test", {"input_token": 10, "reasoning_token": 3}, snapshot=snapshot)

    assert (exact.known_cost_usd, exact.cost_quality, exact.cost_source, exact.applied_rates_usd) == (
        Decimal("0.75"),
        "exact",
        "provider_response",
        {},
    )
    assert (estimated.known_cost_usd, estimated.cost_quality, estimated.cost_source, estimated.applied_rates_usd) == (
        Decimal("0.014"),
        "estimated",
        "models.dev",
        {"input_token": Decimal("0.001"), "output_token": Decimal("0.002")},
    )
    assert (partial.known_cost_usd, partial.cost_quality, partial.cost_source, partial.applied_rates_usd) == (
        Decimal("0.010"),
        "unknown",
        "unknown",
        {"input_token": Decimal("0.001")},
    )
    assert "reasoning_token" not in partial.applied_rates_usd
    assert calculate_cost("openai", "gpt-test", {}, snapshot=snapshot).cost_quality == "unknown"


def test_manual_character_rate_estimates_streaming_tts_cost() -> None:
    snapshot = PriceSnapshot(
        fetched_at="2026-08-11T12:00:00Z",
        models={
            "openai/gpt-4o-mini-tts": ModelPrice(
                source="manual",
                source_url=None,
                source_model_id="gpt-4o-mini-tts",
                last_successful_at=None,
                stale=False,
                rates_usd={"character": Decimal("0.0001")},
            )
        },
    )

    result = calculate_cost("openai", "gpt-4o-mini-tts", {"character": 12}, snapshot=snapshot)

    assert result.known_cost_usd == Decimal("0.0012")
    assert result.cost_quality == "estimated"
    assert result.cost_source == "manual"


@pytest.mark.asyncio
async def test_ordinary_scope_owns_one_summary_and_preserves_accounting(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    records = []

    async with track_model_costs("ocr"):
        records.append(record_model_interaction("exact", "openai", "gpt-test", "completed", provider_cost_usd="0.1"))
        records.append(record_model_interaction("estimated", "openai", "gpt-test", "completed", {"input_token": 1}))
        records.append(record_model_interaction("unknown", "openai", "missing", "failed", {"input_token": 1}))

    assert all(record is not None for record in records)
    assert aggregate_quality(records) == "unknown"
    assert caplog.text.count("model_cost stage=final") == 1
    assert "operation=ocr" in caplog.text
    assert "status=completed_with_errors" in caplog.text
    assert "known_total_usd=0.10100000" in caplog.text
    assert 'cost_breakdown_usd={"estimated":"0.00100000","exact":"0.10000000","unknown":"0.00000000"}' in caplog.text
    assert 'applied_rates_usd={"input_token":"0.00100000"}' in caplog.text
    assert "component=exact" in caplog.text and "applied_rates_usd={}" in caplog.text
    assert "exact_calls=1 estimated_calls=1 unknown_calls=1" in caplog.text


@pytest.mark.asyncio
async def test_summary_aggregates_repeated_components_with_stable_usd_format(caplog) -> None:
    caplog.set_level(logging.INFO)

    async with track_model_costs("voice"):
        record_model_interaction("tts", "openai", "gpt-test", "completed", {"input_token": 1})
        record_model_interaction("tts", "openai", "gpt-test", "completed", provider_cost_usd="0.2")

    assert "known_total_usd=0.20100000" in caplog.text
    assert 'cost_breakdown_usd={"tts":"0.20100000"}' in caplog.text


@pytest.mark.asyncio
async def test_cached_input_write_rate_is_applied_and_visible_at_debug(caplog) -> None:
    caplog.set_level(logging.DEBUG)

    async with track_model_costs("chat"):
        record = record_model_interaction(
            "teacher",
            "openai",
            "gpt-test",
            "completed",
            {"cached_input_write_token": 4},
        )

    assert record is not None
    assert record.known_cost_usd == Decimal("0.0016")
    assert record.applied_rates_usd == {"cached_input_write_token": Decimal("0.0004")}
    assert 'applied_rates_usd={"cached_input_write_token":"0.00040000"}' in caplog.text
    assert "known_cost_usd=0.00160000" in caplog.text
    assert "known_total_usd=0.00160000" in caplog.text


@pytest.mark.asyncio
async def test_nested_scope_inherits_parent_without_duplicate_summary_and_warns(caplog) -> None:
    caplog.set_level(logging.WARNING)

    async with track_model_costs("parent"):
        async with track_model_costs("requested-child"):
            record = record_model_interaction("child", "openai", "gpt-test", "completed", {"input_token": 1})

    assert record is not None
    assert record.operation_type == "parent"
    assert record.phase == "foreground"
    assert caplog.text.count("nested tracking inherited active collector") == 1
    assert "requested_activity=requested-child active_activity=parent" in caplog.text
    assert "input_token" not in caplog.text


@pytest.mark.asyncio
async def test_suspended_tracking_allows_inner_scope_to_own_separate_summary(caplog) -> None:
    caplog.set_level(logging.INFO)

    async with track_model_costs("chat"):
        with suspend_model_cost_tracking():
            async with track_model_costs("memory_maintenance"):
                record_model_interaction("memory", "openai", "gpt-test", "completed", {"input_token": 1})

    assert caplog.text.count("model_cost stage=final") == 2
    assert caplog.text.count("operation=memory_maintenance") == 1
    assert caplog.text.count("operation=chat") == 1


@pytest.mark.asyncio
async def test_suspended_tracking_restores_prior_binding_after_exit() -> None:
    async with track_model_costs("chat"):
        before = record_model_interaction("before", "openai", "gpt-test", "completed", {"input_token": 1})
        with suspend_model_cost_tracking():
            assert record_model_interaction("detached", "openai", "gpt-test", "completed") is None
        after = record_model_interaction("after", "openai", "gpt-test", "completed", {"input_token": 1})

    assert before is not None
    assert after is not None
    assert after.operation_id == before.operation_id
    assert after.operation_type == "chat"


@pytest.mark.asyncio
async def test_concurrent_ordinary_scopes_are_isolated() -> None:
    async def work(activity: str) -> tuple[str, str]:
        async with track_model_costs(activity):
            await asyncio.sleep(0)
            record = record_model_interaction(activity, "openai", "gpt-test", "completed", {"input_token": 1})
            assert record is not None
            return record.operation_type, record.operation_id

    first, second = await asyncio.gather(work("first"), work("second"))

    assert first[0] == "first"
    assert second[0] == "second"
    assert first[1] != second[1]


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [(asyncio.CancelledError, "cancelled"), (asyncio.TimeoutError, "timed_out"), (RuntimeError, "failed")],
)
@pytest.mark.asyncio
async def test_ordinary_exception_status(exception: type[BaseException], expected_status: str, caplog) -> None:
    caplog.set_level(logging.INFO)
    with pytest.raises(exception):
        async with track_model_costs("ordinary"):
            raise exception("stopped")

    assert caplog.text.count("stage=final") == 1
    assert f"status={expected_status}" in caplog.text


def test_ambient_recorder_is_content_free_and_fail_open(caplog) -> None:
    caplog.set_level(logging.WARNING)
    record = record_model_interaction(
        "voice", "openai", "gpt-test", "completed", {"input_token": 123}, provider_cost_usd="4.56"
    )

    assert record is None
    assert "component=voice provider=openai model=gpt-test status=completed" in caplog.text
    assert "123" not in caplog.text
    assert "4.56" not in caplog.text


@pytest.mark.asyncio
async def test_handle_validation_idempotency_and_read_only_properties() -> None:
    async with track_model_costs_with_background("chat") as controller:
        handle = controller.transfer("post_turn")
        assert isinstance(handle, CostTrackingHandle)
        assert handle.name == "post_turn"
        assert handle.status is None
        with pytest.raises(ValueError, match="Invalid handle status"):
            handle.finish("not-a-status")
        assert handle.finish("completed") is True
        assert handle.finish("failed") is False
        assert handle.status == "completed"
        with pytest.raises(AttributeError):
            handle.name = "changed"
        assert not hasattr(handle, "__aenter__")


@pytest.mark.asyncio
async def test_handle_activation_restores_prior_binding() -> None:
    async with track_model_costs_with_background("chat") as controller:
        handle = controller.transfer("memory")
        foreground = record_model_interaction("teacher", "openai", "gpt-test", "completed", {"input_token": 1})
        with handle.activate():
            background = record_model_interaction("memory", "openai", "gpt-test", "completed", {"input_token": 2})
        restored = record_model_interaction("teacher-2", "openai", "gpt-test", "completed", {"input_token": 3})
        handle.finish("completed")

    assert foreground is not None and foreground.phase == "foreground"
    assert background is not None and background.phase == "background"
    assert restored is not None and restored.phase == "foreground"


@pytest.mark.asyncio
async def test_background_success_orders_preliminary_before_exactly_one_correction(caplog) -> None:
    caplog.set_level(logging.INFO)
    async with track_model_costs_with_background("chat") as controller:
        first = controller.transfer("post_turn")
        second = controller.transfer("tts")
        record_model_interaction("teacher", "openai", "gpt-test", "completed", {"input_token": 2})

    with first.activate():
        record_model_interaction("memory", "openai", "gpt-test", "completed", {"input_token": 3})
    assert first.finish("completed") is True
    assert "stage=corrected" not in caplog.text
    with second.activate():
        record_model_interaction("tts", "openai", "gpt-test", "completed", provider_cost_usd="0.5")
    assert second.finish("skipped_no_websocket") is True
    assert second.finish("completed") is False

    assert caplog.text.count("stage=preliminary") == 1
    assert caplog.text.count("stage=corrected") == 1
    assert caplog.text.index("stage=preliminary") < caplog.text.index("stage=corrected")
    assert "known_foreground_usd=0.00200000" in caplog.text
    assert "known_background_usd=0.50300000" in caplog.text
    assert "known_total_usd=0.50500000" in caplog.text
    assert "stage=preliminary" in caplog.text
    assert 'cost_breakdown_usd={"teacher":"0.00200000"}' in caplog.text
    assert 'cost_breakdown_usd={"memory":"0.00300000","teacher":"0.00200000","tts":"0.50000000"}' in caplog.text


@pytest.mark.asyncio
async def test_background_preliminary_is_immutable_when_handle_finishes_early(caplog) -> None:
    caplog.set_level(logging.INFO)
    async with track_model_costs_with_background("chat") as controller:
        handle = controller.transfer("post_turn")
        with handle.activate():
            record_model_interaction("early", "openai", "gpt-test", "completed", {"input_token": 3})
        handle.finish("completed")
        record_model_interaction("teacher", "openai", "gpt-test", "completed", {"input_token": 2})

    assert caplog.text.index("stage=preliminary") < caplog.text.index("stage=corrected")
    assert "stage=preliminary" in caplog.text and "known_foreground_usd=0.00200000" in caplog.text
    assert caplog.text.count("stage=corrected") == 1


@pytest.mark.asyncio
async def test_background_exception_seals_handles_and_emits_only_failure(caplog) -> None:
    caplog.set_level(logging.INFO)
    with pytest.raises(RuntimeError):
        async with track_model_costs_with_background("chat") as controller:
            handle = controller.transfer("post_turn")
            record_model_interaction("teacher", "openai", "gpt-test", "completed", {"input_token": 2})
            raise RuntimeError("failed")

    assert handle.status == "cancelled_with_unknown_usage"
    assert handle.finish("completed") is False
    assert caplog.text.count("model_cost stage=final") == 1
    assert "status=failed" in caplog.text
    assert "cost_quality=unknown" in caplog.text
    assert "unknown_calls=1" in caplog.text
    assert "stage=preliminary" not in caplog.text
    assert "stage=corrected" not in caplog.text


def test_recording_and_logging_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_log(level: int, message: str, args: object) -> None:
        raise RuntimeError("logging unavailable")

    monkeypatch.setattr("runestone.model_costs.tracking.logger.log", fail_log)
    monkeypatch.setattr("runestone.model_costs.tracking.logger.warning", fail_log)
    assert record_model_interaction("orphan", "openai", "gpt-test", "completed") is None
