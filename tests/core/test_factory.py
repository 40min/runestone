"""
Tests for LLM client factory.

This module tests the factory functions for creating LLM clients,
ensuring proper API key validation and client instantiation.
"""

from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.clients.factory import (
    _create_gemini_client,
    _create_openai_client,
    create_llm_client,
    get_available_providers,
)
from runestone.core.exceptions import APIKeyError


class TestFactory:
    """Test cases for LLM client factory functions."""

    def test_get_available_providers(self):
        """Test get_available_providers returns correct list."""
        providers = get_available_providers()
        assert providers == ["openai", "gemini"]

    @patch("runestone.core.clients.factory.OpenAIClient")
    def test_create_openai_client_success(self, mock_openai_client):
        """Test successful OpenAI client creation."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = "test-key"
        mock_client = Mock()
        mock_openai_client.return_value = mock_client

        result = _create_openai_client(mock_settings, "gpt-4", True)

        assert result == mock_client
        mock_openai_client.assert_called_once_with(api_key="test-key", model_name="gpt-4", verbose=True)

    def test_create_openai_client_missing_api_key(self):
        """Test OpenAI client creation fails with missing API key."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = ""

        with pytest.raises(APIKeyError) as exc_info:
            _create_openai_client(mock_settings, None, False)

        assert "OpenAI API key is required" in str(exc_info.value)

    @patch("runestone.core.clients.factory.OpenAIClient")
    def test_create_openai_client_no_model_name(self, mock_openai_client):
        """Test OpenAI client creation without model name."""
        mock_settings = Mock(spec=Settings)
        mock_settings.openai_api_key = "test-key"
        mock_client = Mock()
        mock_openai_client.return_value = mock_client

        result = _create_openai_client(mock_settings, None, False)

        assert result == mock_client
        mock_openai_client.assert_called_once_with(api_key="test-key", verbose=False)

    @patch("runestone.core.clients.factory.GeminiClient")
    def test_create_gemini_client_success(self, mock_gemini_client):
        """Test successful Gemini client creation."""
        mock_settings = Mock(spec=Settings)
        mock_settings.gemini_api_key = "test-key"
        mock_client = Mock()
        mock_gemini_client.return_value = mock_client

        result = _create_gemini_client(mock_settings, True)

        assert result == mock_client
        mock_gemini_client.assert_called_once_with(api_key="test-key", verbose=True)

    def test_create_gemini_client_missing_api_key(self):
        """Test Gemini client creation fails with missing API key."""
        mock_settings = Mock(spec=Settings)
        mock_settings.gemini_api_key = ""

        with pytest.raises(APIKeyError) as exc_info:
            _create_gemini_client(mock_settings, False)

        assert "Gemini API key is required" in str(exc_info.value)

    @patch("runestone.core.clients.factory._create_openai_client")
    def test_create_llm_client_openai(self, mock_create_openai):
        """Test create_llm_client for OpenAI provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.llm_model_name = "gpt-4"
        mock_settings.verbose = True
        mock_client = Mock()
        mock_create_openai.return_value = mock_client

        result = create_llm_client(mock_settings)

        assert result == mock_client
        mock_create_openai.assert_called_once_with(settings=mock_settings, model_name="gpt-4", verbose=True)

    @patch("runestone.core.clients.factory._create_gemini_client")
    def test_create_llm_client_gemini(self, mock_create_gemini):
        """Test create_llm_client for Gemini provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "gemini"
        mock_settings.verbose = False
        mock_client = Mock()
        mock_create_gemini.return_value = mock_client

        result = create_llm_client(mock_settings)

        assert result == mock_client
        mock_create_gemini.assert_called_once_with(settings=mock_settings, verbose=False)

    def test_create_llm_client_unsupported_provider(self):
        """Test create_llm_client fails with unsupported provider."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "unsupported"
        mock_settings.verbose = False

        with pytest.raises(ValueError) as exc_info:
            create_llm_client(mock_settings)

        assert "Unsupported LLM provider: unsupported" in str(exc_info.value)
