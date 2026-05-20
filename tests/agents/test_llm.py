"""
Tests for the LLM factory.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from runestone.agents.llm import DEFAULT_AGENT_LLM_TIMEOUT_SECONDS, DEFAULT_AGENT_MAX_RETRIES, build_chat_model
from runestone.config import AgentLLMSettings, ReasoningLevel, Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.openrouter_api_key = "test-openrouter-key"
    settings.openai_api_key = "test-openai-key"
    settings.gemini_api_key = "test-gemini-key"
    settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openrouter",
        model="test-chat-model",
        temperature=0.3,
        reasoning_level=ReasoningLevel.NONE,
    )
    return settings


def test_build_chat_model_openrouter(mock_settings):
    """Test building a model with OpenRouter provider."""
    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings, "teacher")

        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "test-chat-model"
        assert call_kwargs["api_key"] == SecretStr("test-openrouter-key")
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["timeout"] == DEFAULT_AGENT_LLM_TIMEOUT_SECONDS
        assert "extra_body" not in call_kwargs
        mock_settings.get_agent_llm_settings.assert_called_once_with("teacher")


def test_build_chat_model_openai(mock_settings):
    """Test building a model with OpenAI provider."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openai",
        model="test-chat-model",
        temperature=0.1,
        reasoning_level=ReasoningLevel.NONE,
    )

    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings, "coordinator")

        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "test-chat-model"
        assert call_kwargs["api_key"] == SecretStr("test-openai-key")
        assert call_kwargs.get("base_url") is None
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["timeout"] == DEFAULT_AGENT_LLM_TIMEOUT_SECONDS


def test_build_chat_model_gemini(mock_settings):
    """Test building a model with Gemini provider."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="gemini",
        model="gemini-2.5-flash",
        temperature=0.2,
        reasoning_level=ReasoningLevel.NONE,
    )

    with patch("runestone.agents.llm.ChatGoogleGenerativeAI") as mock_chat_gemini:
        build_chat_model(mock_settings, "coordinator")

        mock_chat_gemini.assert_called_once()
        call_kwargs = mock_chat_gemini.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert call_kwargs["api_key"] == SecretStr("test-gemini-key")
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["timeout"] == DEFAULT_AGENT_LLM_TIMEOUT_SECONDS
        assert call_kwargs["max_retries"] == DEFAULT_AGENT_MAX_RETRIES
        assert call_kwargs["disable_streaming"] == "tool_calling"
        assert "thinking_level" not in call_kwargs


def test_build_chat_model_gemini_25_ignores_thinking_level_when_reasoning_configured(mock_settings):
    """Gemini 2.5 should not receive thinking_level."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="gemini",
        model="gemini-2.5-flash",
        temperature=0.2,
        reasoning_level=ReasoningLevel.MINIMAL,
    )

    with patch("runestone.agents.llm.ChatGoogleGenerativeAI") as mock_chat_gemini:
        build_chat_model(mock_settings, "coordinator")

        call_kwargs = mock_chat_gemini.call_args[1]
        assert "thinking_level" not in call_kwargs


def test_build_chat_model_gemini_3_adds_thinking_level_when_reasoning_configured(mock_settings):
    """Gemini 3 models should map reasoning_level to thinking_level."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="gemini",
        model="gemini-3-flash-preview",
        temperature=0.2,
        reasoning_level=ReasoningLevel.MINIMAL,
    )

    with patch("runestone.agents.llm.ChatGoogleGenerativeAI") as mock_chat_gemini:
        build_chat_model(mock_settings, "coordinator")

        call_kwargs = mock_chat_gemini.call_args[1]
        assert call_kwargs["thinking_level"] == "minimal"


def test_build_chat_model_adds_openrouter_reasoning_when_configured(mock_settings):
    """Test reasoning is derived from config instead of hardcoded model logic."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openrouter",
        model="google/gemini-3-flash-preview",
        temperature=0.0,
        reasoning_level=ReasoningLevel.MINIMAL,
    )

    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings, "coordinator")

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["extra_body"] == {"reasoning": {"effort": "minimal"}}


def test_build_chat_model_does_not_send_reasoning_when_disabled(mock_settings):
    """Test reasoning settings are omitted when set to none."""
    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings, "word_keeper")

        call_kwargs = mock_chat_openai.call_args[1]
        assert "extra_body" not in call_kwargs


def test_build_chat_model_supports_news_agent(mock_settings):
    """Test news_agent uses the standard per-agent config path."""
    with patch("runestone.agents.llm.ChatOpenAI"):
        build_chat_model(mock_settings, "news_agent")

    mock_settings.get_agent_llm_settings.assert_called_once_with("news_agent")


def test_build_chat_model_supports_memory_maintainer(mock_settings):
    """Test memory_maintainer uses the standard per-agent config path."""
    with patch("runestone.agents.llm.ChatOpenAI"):
        build_chat_model(mock_settings, "memory_maintainer")

    mock_settings.get_agent_llm_settings.assert_called_once_with("memory_maintainer")


def test_build_chat_model_allows_timeout_override(mock_settings):
    """Test build_chat_model allows callers to override the default timeout."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="gemini",
        model="gemini-2.5-flash",
        temperature=0.2,
        reasoning_level=ReasoningLevel.NONE,
    )

    with patch("runestone.agents.llm.ChatGoogleGenerativeAI") as mock_chat_gemini:
        build_chat_model(mock_settings, "teacher", timeout_seconds=3.0)

        call_kwargs = mock_chat_gemini.call_args[1]
        assert call_kwargs["timeout"] == 3.0


def test_build_chat_model_unsupported_provider(mock_settings):
    """Test that unsupported provider raises ValueError."""
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings.model_construct(
        provider="unsupported",
        model="test-chat-model",
        temperature=0.0,
        reasoning_level=ReasoningLevel.NONE,
    )
    with pytest.raises(ValueError, match="Unsupported chat provider: unsupported"):
        build_chat_model(mock_settings, "teacher")


def test_build_chat_model_missing_api_key(mock_settings):
    """Test that missing API key raises ValueError."""
    for provider_name, attr_name in (
        ("openai", "openai_api_key"),
        ("openrouter", "openrouter_api_key"),
        ("gemini", "gemini_api_key"),
    ):
        mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
            provider=provider_name,
            model="test-chat-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
        )
        setattr(mock_settings, attr_name, None)
        with pytest.raises(ValueError, match=f"API key for {provider_name} is not configured"):
            build_chat_model(mock_settings, "teacher")
        setattr(mock_settings, attr_name, f"restored-{provider_name}-key")
