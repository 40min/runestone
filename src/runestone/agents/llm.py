"""
LLM factory for agent models.
"""

import logging
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from runestone.config import ReasoningLevel, Settings

logger = logging.getLogger(__name__)

AgentName = Literal["teacher", "coordinator", "word_keeper", "news_agent", "memory_keeper"]


def build_chat_model(settings: Settings, agent_name: AgentName) -> ChatOpenAI:
    """Build a ChatOpenAI instance from validated per-agent configuration."""
    agent_settings = settings.get_agent_llm_settings(agent_name)

    if agent_settings.provider == "openrouter":
        api_key = settings.openrouter_api_key
        api_base = "https://openrouter.ai/api/v1"
    elif agent_settings.provider == "openai":
        api_key = settings.openai_api_key
        api_base = None
    else:
        raise ValueError(f"Unsupported chat provider: {agent_settings.provider}")

    if not api_key:
        raise ValueError(f"API key for {agent_settings.provider} is not configured")

    extra_kwargs = {}
    if agent_settings.provider == "openrouter" and agent_settings.reasoning_level != ReasoningLevel.NONE:
        extra_kwargs["extra_body"] = {"reasoning": {"effort": agent_settings.reasoning_level.value}}

    logger.debug(
        "[agents:llm] Building ChatOpenAI model: agent=%s, provider=%s, model=%s, temp=%.2f, reasoning=%s",
        agent_name,
        agent_settings.provider,
        agent_settings.model,
        agent_settings.temperature,
        agent_settings.reasoning_level.value,
    )

    return ChatOpenAI(
        model=agent_settings.model,
        api_key=SecretStr(api_key),
        base_url=api_base,
        temperature=agent_settings.temperature,
        **extra_kwargs,
    )
