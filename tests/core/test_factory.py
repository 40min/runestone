"""
Tests for LLM client factory.

This module tests the factory functions for creating LLM clients,
ensuring proper API key validation and client instantiation.
"""

from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.clients.factory import (
    _create_openai_client,
    _create_openrouter_client,
    create_llm_client,
    get_available_providers,
)
from runestone.core.exceptions import APIKeyError


class TestFactory:
    """Test cases for LLM client factory functions."""

    def test_get_available_providers(self):
        """Test get_available_providers returns correct list."""
        providers = get_available_providers()
        assert providers == ["openai", "openrouter"]

    @patch("runestone.core.clients.factory.OpenAIClient")
    def test_create_openai_client_success(self, mock_openai_client):
        """Test successful OpenAI client creation."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = "test-key"
        mock_settings.verbose = True
        mock_client = Mock()
        mock_openai_client.return_value = mock_client

        result = _create_openai_client(mock_settings, "gpt-4")

        assert result == mock_client
        mock_openai_client.assert_called_once_with(api_key="test-key", model_name="gpt-4", verbose=True)

    def test_create_openai_client_missing_api_key(self):
        """Test OpenAI client creation fails with missing API key."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = ""

        with pytest.raises(APIKeyError) as exc_info:
            _create_openai_client(mock_settings, None)

        assert "OpenAI API key is required" in str(exc_info.value)

    @patch("runestone.core.clients.factory.OpenAIClient")
    def test_create_openai_client_no_model_name(self, mock_openai_client):
        """Test OpenAI client creation without model name."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = "test-key"
        mock_settings.verbose = False
        mock_client = Mock()
        mock_openai_client.return_value = mock_client

        result = _create_openai_client(mock_settings, None)

        assert result == mock_client
        mock_openai_client.assert_called_once_with(api_key="test-key", verbose=False)

    @patch("runestone.core.clients.factory.OpenRouterClient")
    def test_create_openrouter_client_success(self, mock_openrouter_client):
        """Test successful OpenRouter client creation."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openrouter_api_key = "test-key"
        mock_settings.verbose = True
        mock_client = Mock()
        mock_openrouter_client.return_value = mock_client

        result = _create_openrouter_client(mock_settings, "anthropic/claude-3.5-sonnet")

        assert result == mock_client
        mock_openrouter_client.assert_called_once_with(
            api_key="test-key", model_name="anthropic/claude-3.5-sonnet", verbose=True
        )

    def test_create_openrouter_client_missing_api_key(self):
        """Test OpenRouter client creation fails with missing API key."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openrouter_api_key = ""

        with pytest.raises(APIKeyError) as exc_info:
            _create_openrouter_client(mock_settings, None)

        assert "OpenRouter API key is required" in str(exc_info.value)

    @patch("runestone.core.clients.factory.OpenRouterClient")
    def test_create_openrouter_client_no_model_name(self, mock_openrouter_client):
        """Test OpenRouter client creation without model name."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openrouter_api_key = "test-key"
        mock_settings.verbose = False
        mock_client = Mock()
        mock_openrouter_client.return_value = mock_client

        result = _create_openrouter_client(mock_settings, None)

        assert result == mock_client
        mock_openrouter_client.assert_called_once_with(api_key="test-key", verbose=False)

    @patch("runestone.core.clients.factory._create_openai_client")
    def test_create_llm_client_openai(self, mock_create_openai):
        """Test create_llm_client for OpenAI provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4"
        mock_client = Mock()
        mock_create_openai.return_value = mock_client

        result = create_llm_client(mock_settings)

        assert result == mock_client
        mock_create_openai.assert_called_once_with(settings=mock_settings, model_name="gpt-4")

    @patch("runestone.core.clients.factory._create_openrouter_client")
    def test_create_llm_client_openrouter(self, mock_create_openrouter):
        """Test create_llm_client for OpenRouter provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openrouter"
        mock_settings.llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_client = Mock()
        mock_create_openrouter.return_value = mock_client

        result = create_llm_client(mock_settings)

        assert result == mock_client
        mock_create_openrouter.assert_called_once_with(settings=mock_settings, model_name="anthropic/claude-3.5-sonnet")

    @patch("runestone.core.clients.factory._create_openai_client")
    def test_create_llm_client_with_provider_override(self, mock_create_openai):
        """Test create_llm_client with provider parameter override."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openrouter"  # Default provider
        mock_settings.llm_model_name = "gpt-4"
        mock_client = Mock()
        mock_create_openai.return_value = mock_client

        result = create_llm_client(mock_settings, provider="openai")

        assert result == mock_client
        mock_create_openai.assert_called_once_with(settings=mock_settings, model_name="gpt-4")

    @patch("runestone.core.clients.factory._create_openai_client")
    def test_create_llm_client_with_model_name_override(self, mock_create_openai):
        """Test create_llm_client with model_name parameter override."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4"  # Default model
        mock_client = Mock()
        mock_create_openai.return_value = mock_client

        result = create_llm_client(mock_settings, model_name="gpt-3.5-turbo")

        assert result == mock_client
        mock_create_openai.assert_called_once_with(settings=mock_settings, model_name="gpt-3.5-turbo")

    @patch("runestone.core.clients.factory._create_openrouter_client")
    def test_create_llm_client_with_both_overrides(self, mock_create_openrouter):
        """Test create_llm_client with both provider and model_name overrides."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"  # Default provider
        mock_settings.llm_model_name = "gpt-4"  # Default model
        mock_client = Mock()
        mock_create_openrouter.return_value = mock_client

        result = create_llm_client(mock_settings, provider="openrouter", model_name="anthropic/claude-3.5-sonnet")

        assert result == mock_client
        mock_create_openrouter.assert_called_once_with(settings=mock_settings, model_name="anthropic/claude-3.5-sonnet")

    def test_create_llm_client_unsupported_provider(self):
        """Test create_llm_client fails with unsupported provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "unsupported"
        mock_settings.llm_model_name = None

        with pytest.raises(ValueError) as exc_info:
            create_llm_client(mock_settings)

        assert "Unsupported LLM provider: unsupported" in str(exc_info.value)
