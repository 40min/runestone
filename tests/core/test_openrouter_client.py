"""
Tests for the OpenRouter client module.
"""

from unittest.mock import Mock, patch

import pytest
from openai import APIError

from runestone.core.clients.openrouter_client import OpenRouterClient
from runestone.core.exceptions import APIKeyError, LLMError


class TestOpenRouterClient:
    """Test cases for OpenRouterClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "Improve this vocabulary item"

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_instantiation_success(self, mock_openai_class):
        """Test that OpenRouterClient can be instantiated correctly with an API key."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        assert client.api_key == self.api_key
        assert client.client == mock_client
        mock_openai_class.assert_called_once_with(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_configure_client_sets_correct_base_url(self, mock_openai_class):
        """Test that _configure_client() sets up the OpenAI client with correct base_url."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        # Verify the OpenAI client was created with the correct base_url
        mock_openai_class.assert_called_once_with(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        assert client.client == mock_client

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_provider_name_returns_openrouter(self, mock_openai_class):
        """Test that provider_name property returns 'openrouter'."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        assert client.provider_name == "openrouter"

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_configuration_error_handling(self, mock_openai_class):
        """Test error handling when API key configuration fails."""
        mock_openai_class.side_effect = Exception("Configuration failed")

        with pytest.raises(APIKeyError) as exc_info:
            OpenRouterClient(api_key=self.api_key)

        assert "Failed to configure OpenRouter API" in str(exc_info.value)
        assert "Configuration failed" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_improve_vocabulary_item_success(self, mock_openai_class):
        """Test successful vocabulary improvement via OpenRouter."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved vocabulary data"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)
        result = client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_improve_vocabulary_item_no_response(self, mock_openai_class):
        """Test vocabulary improvement with no response text."""
        # Mock response with no content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "No vocabulary improvement returned from OpenAI" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_improve_vocabulary_item_api_error(self, mock_openai_class):
        """Test vocabulary improvement with OpenRouter API error."""
        mock_client = Mock()
        mock_request = Mock()
        mock_client.chat.completions.create.side_effect = APIError("API error", request=mock_request, body=None)
        mock_openai_class.return_value = mock_client

        client = OpenRouterClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "OpenAI API error during vocabulary improvement: API error" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.OpenAI")
    def test_instantiation_with_model_name(self, mock_openai_class):
        """Test OpenRouterClient instantiation with custom model name."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        model_name = "anthropic/claude-3.5-sonnet"

        client = OpenRouterClient(api_key=self.api_key, model_name=model_name)

        assert client.api_key == self.api_key
        assert client.model_name == model_name
        mock_openai_class.assert_called_once_with(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
