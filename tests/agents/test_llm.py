"""
Tests for the LLM factory.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from runestone.agents.llm import build_chat_model
from runestone.config import AgentLLMSettings, ReasoningLevel, Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.openrouter_api_key = "test-openrouter-key"
    settings.openai_api_key = "test-openai-key"
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
    mock_settings.get_agent_llm_settings.return_value = AgentLLMSettings(
        provider="openai",
        model="test-chat-model",
        temperature=0.0,
        reasoning_level=ReasoningLevel.NONE,
    )
    mock_settings.openai_api_key = None
    with pytest.raises(ValueError, match="API key for openai is not configured"):
        build_chat_model(mock_settings, "teacher")
