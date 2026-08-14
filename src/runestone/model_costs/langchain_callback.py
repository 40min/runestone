"""LangChain callback that records standardized, content-free token usage."""

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, UsageMetadata
from langchain_core.outputs import ChatGeneration, LLMResult

from runestone.model_costs.tracking import record_model_interaction

logger = logging.getLogger(__name__)


def _first_ai_message(response: LLMResult) -> AIMessage | None:
    for generation_group in response.generations:
        for generation in generation_group:
            if isinstance(generation, ChatGeneration) and isinstance(generation.message, AIMessage):
                return generation.message
    return None


def _detail_tokens(details: object, key: str) -> int | None:
    if not isinstance(details, dict):
        return None
    value = details.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _normalized_side(
    base_unit: str,
    total: int,
    details: tuple[tuple[str, int | None], ...],
) -> dict[str, int]:
    """Split a total into base and detail units only when the side is coherent."""
    present_details = [(unit, value) for unit, value in details if value is not None]
    detail_total = sum(value for _, value in present_details)
    if detail_total > total:
        return {base_unit: total}
    return {base_unit: total - detail_total, **dict(present_details)}


def _usage_from_metadata(metadata: UsageMetadata) -> dict[str, int]:
    input_details = metadata.get("input_token_details")
    output_details = metadata.get("output_token_details")
    cached_read_tokens = _detail_tokens(input_details, "cache_read")
    cached_write_tokens = _detail_tokens(input_details, "cache_creation")
    input_audio_tokens = _detail_tokens(input_details, "audio")
    reasoning_tokens = _detail_tokens(output_details, "reasoning")
    output_audio_tokens = _detail_tokens(output_details, "audio")

    input_usage = _normalized_side(
        "input_token",
        metadata["input_tokens"],
        (
            ("cached_input_token", cached_read_tokens),
            ("cached_input_write_token", cached_write_tokens),
            ("input_audio_token", input_audio_tokens),
        ),
    )
    output_usage = _normalized_side(
        "output_token",
        metadata["output_tokens"],
        (("reasoning_token", reasoning_tokens), ("output_audio_token", output_audio_tokens)),
    )
    return input_usage | output_usage


def extract_usage(response: LLMResult) -> dict[str, int]:
    """Extract standardized usage from the first returned AI message."""
    message = _first_ai_message(response)
    if message is None or message.usage_metadata is None:
        return {}
    return _usage_from_metadata(message.usage_metadata)


class LangChainCostCallback(BaseCallbackHandler):
    """Record each LangChain completion against the current cost operation."""

    run_inline = True

    def __init__(self, *, provider: str, model: str, component: str) -> None:
        self.provider = provider
        self.model = model
        self.component = component

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Record standardized returned usage without affecting model results."""
        del run_id, parent_run_id, kwargs
        try:
            record_model_interaction(
                component=self.component,
                provider=self.provider,
                model=self.model,
                status="completed",
                usage=extract_usage(response),
                provider_cost_usd=None,
            )
        except Exception as exc:  # pragma: no cover - defensive callback boundary
            try:
                logger.warning(
                    "Model cost LangChain completion recording failed component=%s error=%s", self.component, exc
                )
            except Exception:
                pass

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Record failed calls with unknown usage and cost."""
        del error, run_id, parent_run_id, kwargs
        record_model_interaction(
            component=self.component,
            provider=self.provider,
            model=self.model,
            status="failed",
            usage={},
            provider_cost_usd=None,
        )
