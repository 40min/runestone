"""LLM factory for agent models."""

import logging
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from runestone.config import ReasoningLevel, Settings

logger = logging.getLogger(__name__)

AgentName = Literal[
    "teacher",
    "coordinator",
    "word_keeper",
    "news_agent",
    "memory_keeper",
    "memory_maintainer",
    "learning_memory_keeper",
    "personal_memory_keeper",
]


def build_chat_model(settings: Settings, agent_name: AgentName) -> BaseChatModel:
    """Build a LangChain chat model from validated per-agent configuration.

    Args:
        settings: Application settings.
        agent_name: Agent identifier used to look up per-agent LLM settings
            (provider, model, temperature, timeout, max_retries).

    Returns:
        Configured LangChain chat model.
    """
    agent_settings = settings.get_agent_llm_settings(agent_name)

    if agent_settings.provider == "openrouter":
        api_key = settings.openrouter_api_key
        api_base = "https://openrouter.ai/api/v1"
    elif agent_settings.provider == "gemini":
        api_key = settings.gemini_api_key
        api_base = None
    elif agent_settings.provider == "openai":
        api_key = settings.openai_api_key
        api_base = None
    else:
        raise ValueError(f"Unsupported chat provider: {agent_settings.provider}")

    if not api_key:
        raise ValueError(f"API key for {agent_settings.provider} is not configured")

    extra_kwargs = {}
    if agent_settings.provider == "openrouter":
        extra_body: dict[str, object] = {}
        if agent_settings.reasoning_level != ReasoningLevel.NONE:
            extra_body["reasoning"] = {"effort": agent_settings.reasoning_level.value}
        disallowed_providers = settings.resolve_openrouter_disallowed_providers()
        if disallowed_providers:
            extra_body["provider"] = {"ignore": disallowed_providers}
        if extra_body:
            extra_kwargs["extra_body"] = extra_body

    logger.debug(
        "[agents:llm] Building chat model: agent=%s, provider=%s, model=%s, temp=%.2f, "
        "timeout=%.1fs, max_retries=%d, reasoning=%s",
        agent_name,
        agent_settings.provider,
        agent_settings.model,
        agent_settings.temperature,
        agent_settings.timeout_seconds,
        agent_settings.max_retries,
        agent_settings.reasoning_level.value,
    )

    if agent_settings.provider == "gemini":
        gemini_kwargs = {}
        # Gemini 3+ supports reasoning levels directly via thinking_level.
        if agent_settings.reasoning_level != ReasoningLevel.NONE and agent_settings.model.startswith("gemini-3"):
            gemini_kwargs["thinking_level"] = agent_settings.reasoning_level.value
        return ChatGoogleGenerativeAI(
            model=agent_settings.model,
            api_key=SecretStr(api_key),
            temperature=agent_settings.temperature,
            timeout=agent_settings.timeout_seconds,
            max_retries=agent_settings.max_retries,
            disable_streaming="tool_calling",
            **gemini_kwargs,
        )

    return ChatOpenAI(
        model=agent_settings.model,
        api_key=SecretStr(api_key),
        base_url=api_base,
        temperature=agent_settings.temperature,
        timeout=agent_settings.timeout_seconds,
        max_retries=agent_settings.max_retries,
        **extra_kwargs,
    )
