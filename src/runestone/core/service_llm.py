"""LangChain chat model builder for non-agent service flows."""

from typing import Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from runestone.config import Settings
from runestone.core.exceptions import APIKeyError

ServiceLLMProvider = Literal["openai", "openrouter"]
SERVICE_LLM_TIMEOUT_SECONDS = 120.0
OPENAI_SERVICE_LLM_MAX_RETRIES = 3


def get_available_service_llm_providers() -> list[str]:
    """Return supported provider names for non-agent LLM flows."""
    return ["openai", "openrouter"]


def build_service_llm_model(
    settings: Settings,
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.1,
) -> BaseChatModel:
    """
    Build a LangChain chat model for non-agent OCR and service flows.

    Args:
        settings: Application settings.
        provider: Optional provider override. Defaults to ``settings.llm_provider``.
        model_name: Optional model override. Defaults to ``settings.llm_model_name``.
        temperature: Sampling temperature for the model.

    Returns:
        Configured LangChain chat model.

    Raises:
        APIKeyError: If the selected provider is not configured.
        ValueError: If the provider is unsupported.
    """
    effective_provider = cast(ServiceLLMProvider, (provider or settings.resolve_service_llm_provider()).lower())
    effective_model_name = model_name or settings.resolve_service_llm_model()

    if effective_provider not in get_available_service_llm_providers():
        raise ValueError(
            f"Unsupported LLM provider: {effective_provider}. "
            f"Supported providers: {', '.join(get_available_service_llm_providers())}"
        )

    if effective_provider == "openrouter":
        api_key = settings.openrouter_api_key
        if not api_key:
            raise APIKeyError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
        return ChatOpenAI(
            model=effective_model_name,
            api_key=SecretStr(api_key),
            temperature=temperature,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://runestone.app",
                "X-Title": "Runestone",
            },
            timeout=SERVICE_LLM_TIMEOUT_SECONDS,
        )

    api_key = settings.openai_api_key
    if not api_key:
        raise APIKeyError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

    return ChatOpenAI(
        model=effective_model_name,
        api_key=SecretStr(api_key),
        temperature=temperature,
        timeout=SERVICE_LLM_TIMEOUT_SECONDS,
        max_retries=OPENAI_SERVICE_LLM_MAX_RETRIES,
    )


def extract_message_text(message: BaseMessage) -> str:
    """
    Extract text content from a LangChain model response.

    LangChain chat models may return plain string content or structured content
    blocks. Non-text blocks are ignored here because the service flows only need
    the textual completion payload.
    """
    if isinstance(message.content, str):
        return message.content.strip()

    parts: list[str] = []
    for block in message.content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)

    return "\n".join(part.strip() for part in parts if part.strip()).strip()
