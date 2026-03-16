"""
LLM factory for agent models.
"""

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from runestone.config import Settings

logger = logging.getLogger(__name__)


def build_chat_model(settings: Settings, model_name: str | None = None, temperature: float = 0.0) -> ChatOpenAI:
    """
    Build a ChatOpenAI instance based on settings.

    Args:
        settings: Application settings.
        model_name: Optional model name override. If not provided, uses settings.chat_model.
        temperature: Sampling temperature.

    Returns:
        ChatOpenAI instance.
    """
    if settings.chat_provider == "openrouter":
        api_key = settings.openrouter_api_key
        api_base = "https://openrouter.ai/api/v1"
    elif settings.chat_provider == "openai":
        api_key = settings.openai_api_key
        api_base = None
    else:
        raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")

    if not api_key:
        raise ValueError(f"API key for {settings.chat_provider} is not configured")

    actual_model = model_name or settings.chat_model

    logger.debug(
        "[agents:llm] Building ChatOpenAI model: provider=%s, model=%s, temp=%.2f",
        settings.chat_provider,
        actual_model,
        temperature,
    )

    return ChatOpenAI(
        model=actual_model,
        api_key=SecretStr(api_key),
        base_url=api_base,
        temperature=temperature,
    )
