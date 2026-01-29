"""
Tests for the OpenRouter client module.
"""

from unittest.mock import Mock, patch

import pytest

from runestone.core.clients.openrouter_client import OpenRouterClient
from runestone.core.exceptions import APIKeyError, LLMError


class TestOpenRouterClient:
    """Test cases for OpenRouterClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "Improve this vocabulary item"

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_instantiation_success(self, mock_openrouter_class):
        """Test that OpenRouterClient can be instantiated correctly with an API key."""
        mock_client = Mock()
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        assert client.api_key == self.api_key
        assert client.client == mock_client
        mock_openrouter_class.assert_called_once_with(api_key=self.api_key)

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_configure_client_initialization(self, mock_openrouter_class):
        """Test that _configure_client() sets up the OpenRouter client."""
        mock_client = Mock()
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        # Verify the OpenRouter client was created
        mock_openrouter_class.assert_called_once_with(api_key=self.api_key)
        assert client.client == mock_client

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_provider_name_returns_openrouter(self, mock_openrouter_class):
        """Test that provider_name property returns 'openrouter'."""
        mock_client = Mock()
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        assert client.provider_name == "openrouter"

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_configuration_error_handling(self, mock_openrouter_class):
        """Test error handling when API key configuration fails."""
        mock_openrouter_class.side_effect = Exception("Configuration failed")

        with pytest.raises(APIKeyError) as exc_info:
            OpenRouterClient(api_key=self.api_key)

        assert "Failed to configure OpenRouter API" in str(exc_info.value)
        assert "Configuration failed" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_improve_vocabulary_item_success(self, mock_openrouter_class):
        """Test successful vocabulary improvement via OpenRouter SDK."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved vocabulary data"

        mock_client = Mock()
        mock_client.chat.send.return_value = mock_response
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)
        result = client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_client.chat.send.assert_called_once()

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_improve_vocabulary_item_no_response(self, mock_openrouter_class):
        """Test vocabulary improvement with no response text."""
        # Mock response with no content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        mock_client = Mock()
        mock_client.chat.send.return_value = mock_response
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert f"No vocabulary improvement returned from {client.provider_name}" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_improve_vocabulary_item_sdk_error(self, mock_openrouter_class):
        """Test vocabulary improvement with OpenRouter SDK error."""
        mock_client = Mock()
        mock_client.chat.send.side_effect = Exception("SDK error")
        mock_openrouter_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "Vocabulary improvement failed: SDK error" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenRouter")
    def test_instantiation_with_model_name(self, mock_openrouter_class):
        """Test OpenRouterClient instantiation with custom model name."""
        mock_client = Mock()
        mock_openrouter_class.return_value = mock_client
        model_name = "anthropic/claude-3.5-sonnet"

        client = OpenRouterClient(api_key=self.api_key, model_name=model_name)

        assert client.api_key == self.api_key
        assert client.model_name == model_name
        mock_openrouter_class.assert_called_once_with(api_key=self.api_key)
