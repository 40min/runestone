"""
Tests for the LLM factory.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from runestone.agents.llm import build_chat_model
from runestone.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.chat_provider = "openrouter"
    settings.chat_model = "test-chat-model"
    settings.openrouter_api_key = "test-openrouter-key"
    settings.openai_api_key = "test-openai-key"
    return settings


def test_build_chat_model_openrouter(mock_settings):
    """Test building a model with OpenRouter provider."""
    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings)

        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "test-chat-model"
        assert call_kwargs["api_key"] == SecretStr("test-openrouter-key")
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["temperature"] == 0.0


def test_build_chat_model_openai(mock_settings):
    """Test building a model with OpenAI provider."""
    mock_settings.chat_provider = "openai"
    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings)

        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "test-chat-model"
        assert call_kwargs["api_key"] == SecretStr("test-openai-key")
        assert call_kwargs.get("base_url") is None


def test_build_chat_model_override_params(mock_settings):
    """Test building a model with parameter overrides."""
    with patch("runestone.agents.llm.ChatOpenAI") as mock_chat_openai:
        build_chat_model(mock_settings, model_name="override-model", temperature=0.7)

        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["model"] == "override-model"
        assert call_kwargs["temperature"] == 0.7


def test_build_chat_model_unsupported_provider(mock_settings):
    """Test that unsupported provider raises ValueError."""
    mock_settings.chat_provider = "unsupported"
    with pytest.raises(ValueError, match="Unsupported chat provider: unsupported"):
        build_chat_model(mock_settings)


def test_build_chat_model_missing_api_key(mock_settings):
    """Test that missing API key raises ValueError."""
    mock_settings.chat_provider = "openai"
    mock_settings.openai_api_key = None
    with pytest.raises(ValueError, match="API key for openai is not configured"):
        build_chat_model(mock_settings)
