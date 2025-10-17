"""
Tests for the OpenAI client module.
"""

from unittest.mock import Mock, patch

import pytest
from openai import APIError

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import LLMError


class TestOpenAIClient:
    """Test cases for OpenAIClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "Improve this vocabulary item"

    @patch("runestone.core.clients.openai_client.OpenAI")
    def test_improve_vocabulary_item_success(self, mock_openai_class):
        """Test successful vocabulary improvement."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved vocabulary data"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenAIClient(api_key=self.api_key)
        result = client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.OpenAI")
    def test_improve_vocabulary_item_no_response(self, mock_openai_class):
        """Test vocabulary improvement with no response text."""
        # Mock response with no content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenAIClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert f"No vocabulary improvement returned from {client.provider_name}" in str(exc_info.value)

    @patch("runestone.core.clients.openai_client.OpenAI")
    def test_improve_vocabulary_item_api_error(self, mock_openai_class):
        """Test vocabulary improvement with OpenAI API error."""
        mock_client = Mock()
        mock_request = Mock()
        mock_client.chat.completions.create.side_effect = APIError("API error", request=mock_request, body=None)
        mock_openai_class.return_value = mock_client

        client = OpenAIClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "OpenAI API error during vocabulary improvement: API error" in str(exc_info.value)

    @patch("runestone.core.clients.openai_client.OpenAI")
    def test_improve_vocabulary_item_general_exception(self, mock_openai_class):
        """Test vocabulary improvement with general exception."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = ValueError("Some other error")
        mock_openai_class.return_value = mock_client

        client = OpenAIClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "Vocabulary improvement failed: Some other error" in str(exc_info.value)
