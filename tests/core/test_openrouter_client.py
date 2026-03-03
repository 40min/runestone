"""
Tests for the OpenRouter client module updated for AsyncOpenAI SDK.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from runestone.core.clients.openrouter_client import OpenRouterClient
from runestone.core.exceptions import APIKeyError, LLMError


class TestOpenRouterClient:
    """Test cases for OpenRouterClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "Improve this vocabulary item"

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    def test_instantiation_success(self, mock_openai_class):
        """Test that OpenRouterClient can be instantiated correctly with an API key."""
        client = OpenRouterClient(api_key=self.api_key)

        assert client.api_key == self.api_key
        assert client._base_url == "https://openrouter.ai/api/v1"
        mock_openai_class.assert_called_once()

        # Verify it was called with openrouter base_url and custom headers
        call_args = mock_openai_class.call_args[1]
        assert call_args["base_url"] == "https://openrouter.ai/api/v1"
        assert "HTTP-Referer" in call_args["default_headers"]
        assert "X-Title" in call_args["default_headers"]

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    def test_instantiation_with_model_name(self, mock_openai_class):
        """Test OpenRouterClient instantiation with custom model name."""
        model_name = "anthropic/claude-3.5-sonnet"
        client = OpenRouterClient(api_key=self.api_key, model_name=model_name)

        assert client.api_key == self.api_key
        assert client.model_name == model_name

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    def test_provider_name_returns_openrouter(self, mock_openai_class):
        """Test that provider_name property returns 'openrouter'."""
        client = OpenRouterClient(api_key=self.api_key)
        assert client.provider_name == "openrouter"

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    def test_configuration_error_handling(self, mock_openai_class):
        """Test error handling when API key configuration fails."""
        mock_openai_class.side_effect = Exception("Configuration failed")

        with pytest.raises(APIKeyError) as exc_info:
            OpenRouterClient(api_key=self.api_key)

        assert "Failed to configure OpenRouter API (Exception): Configuration failed" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_success(self, mock_openai_class):
        """Test successful vocabulary improvement via OpenRouter."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Improved vocabulary data"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenRouterClient(api_key=self.api_key)
        result = await client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_no_response(self, mock_openai_class):
        """Test vocabulary improvement with no response text."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content=None))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenRouterClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_item(self.prompt)

        assert f"No vocabulary improvement returned from {client.provider_name}" in str(exc_info.value)

    @patch("runestone.core.clients.openrouter_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_api_error(self, mock_openai_class):
        """Test vocabulary improvement with OpenRouter API error."""
        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create.side_effect = Exception("OpenRouter API Error")

        client = OpenRouterClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_item(self.prompt)

        assert "Vocabulary improvement failed (Exception): OpenRouter API Error" in str(exc_info.value)
