import logging
from decimal import Decimal
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from runestone.model_costs.langchain_callback import LangChainCostCallback, extract_usage
from runestone.model_costs.pricing import ModelPrice, PriceSnapshot
from runestone.model_costs.tracking import track_model_costs


@pytest.fixture(autouse=True)
def use_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    prices = {
        "input_token": Decimal("0.001"),
        "cached_input_token": Decimal("0.0005"),
        "cached_input_write_token": Decimal("0.0008"),
        "input_audio_token": Decimal("0.004"),
        "output_token": Decimal("0.002"),
        "reasoning_token": Decimal("0.003"),
        "output_audio_token": Decimal("0.005"),
    }
    snapshot = PriceSnapshot(
        fetched_at="2026-08-11T12:00:00Z",
        models={
            provider_model: ModelPrice(
                source="models.dev",
                source_url="https://models.dev/api.json",
                source_model_id=provider_model.split("/", 1)[1],
                last_successful_at="2026-08-11T12:00:00Z",
                stale=False,
                rates_usd=prices,
            )
            for provider_model in ("openai/gpt-test", "gemini/gemini-test")
        },
    )
    monkeypatch.setattr("runestone.model_costs.tracking.load_price_snapshot", lambda path: snapshot)


def response(message: AIMessage) -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_extracts_openai_standardized_usage_and_details() -> None:
    result = response(
        AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "input_token_details": {"cache_read": 10, "cache_creation": 6, "audio": 4},
                "output_token_details": {"reasoning": 5, "audio": 2},
            },
        )
    )

    assert extract_usage(result) == {
        "input_token": 80,
        "output_token": 13,
        "cached_input_token": 10,
        "cached_input_write_token": 6,
        "input_audio_token": 4,
        "reasoning_token": 5,
        "output_audio_token": 2,
    }


def test_extracts_gemini_standardized_usage_without_details() -> None:
    result = response(
        AIMessage(
            content="answer",
            usage_metadata={"input_tokens": 30, "output_tokens": 8, "total_tokens": 38},
        )
    )

    assert extract_usage(result) == {"input_token": 30, "output_token": 8}


def test_malformed_input_details_are_ignored_without_double_counting() -> None:
    result = response(
        AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 3,
                "output_tokens": 7,
                "total_tokens": 10,
                "input_token_details": {"cache_read": 2, "cache_creation": 2, "audio": 1},
            },
        )
    )

    assert extract_usage(result) == {"input_token": 3, "output_token": 7}


def test_malformed_output_details_are_ignored_without_double_counting() -> None:
    result = response(
        AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 7,
                "output_tokens": 3,
                "total_tokens": 10,
                "output_token_details": {"reasoning": 2, "audio": 2},
            },
        )
    )

    assert extract_usage(result) == {"input_token": 7, "output_token": 3}


def test_missing_ai_message_or_usage_is_unknown() -> None:
    human_result = LLMResult(generations=[[ChatGeneration(message=HumanMessage(content="question"))]])

    assert extract_usage(human_result) == {}
    assert extract_usage(response(AIMessage(content="answer"))) == {}


@pytest.mark.asyncio
async def test_callback_records_ambient_standardized_usage_without_provider_cost(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    result = response(
        AIMessage(
            content="SECRET RESPONSE",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "input_token_details": {"cache_read": 10},
                "output_token_details": {"reasoning": 5},
            },
        )
    )
    callback = LangChainCostCallback(provider="openai", model="gpt-test", component="teacher")
    async with track_model_costs("chat"):
        callback.on_llm_end(result, run_id=uuid4())

    assert (
        'usage={"cached_input_token": "10", "input_token": "90", "output_token": "15", ' '"reasoning_token": "5"}'
    ) in caplog.text
    assert "known_cost_usd=0.14000000 cost_quality=estimated" in caplog.text
    assert "provider_response" not in caplog.text
    assert "SECRET RESPONSE" not in caplog.text


@pytest.mark.asyncio
async def test_callback_missing_usage_records_unknown(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    callback = LangChainCostCallback(provider="gemini", model="gemini-test", component="teacher")
    async with track_model_costs("chat"):
        callback.on_llm_end(response(AIMessage(content="answer")), run_id=uuid4())

    assert "component=teacher" in caplog.text
    assert "cost_quality=unknown" in caplog.text


@pytest.mark.asyncio
async def test_callback_error_ignores_response_payload_and_records_unknown(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    callback = LangChainCostCallback(provider="openai", model="gpt-test", component="ocr")
    payload = response(
        AIMessage(
            content="SECRET RESPONSE",
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
    )
    async with track_model_costs("ocr"):
        callback.on_llm_error(RuntimeError("provider failed"), run_id=uuid4(), response=payload)

    assert "component=ocr" in caplog.text
    assert "status=failed" in caplog.text
    assert "cost_quality=unknown" in caplog.text
    assert "SECRET RESPONSE" not in caplog.text


def test_callback_without_ambient_scope_is_fail_open_and_content_free(caplog) -> None:
    caplog.set_level(logging.WARNING)
    callback = LangChainCostCallback(provider="openai", model="gpt-test", component="orphan")
    callback.on_llm_end(
        response(
            AIMessage(
                content="TOP SECRET",
                usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            )
        ),
        run_id=uuid4(),
    )

    assert "without active operation component=orphan" in caplog.text
    assert "TOP SECRET" not in caplog.text
