"""
Tests for the Gemini client module.
"""

from unittest.mock import Mock, patch

import google.api_core.exceptions
import pytest

from runestone.core.clients.gemini_client import GeminiClient
from runestone.core.exceptions import LLMError


class TestGeminiClient:
    """Test cases for GeminiClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "Improve this vocabulary item"

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.protos")
    def test_improve_vocabulary_item_success(self, mock_protos, mock_model_class, mock_configure):
        """Test successful vocabulary improvement."""
        # Mock response
        mock_response = Mock()
        mock_response.text = "Improved vocabulary data"

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        client = GeminiClient(api_key=self.api_key)
        result = client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_model.generate_content.assert_called_once_with(self.prompt)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.protos")
    def test_improve_vocabulary_item_no_response(self, mock_protos, mock_model_class, mock_configure):
        """Test vocabulary improvement with no response text."""
        # Mock response with no text
        mock_response = Mock()
        mock_response.text = None

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        client = GeminiClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "No vocabulary improvement returned from Gemini" in str(exc_info.value)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.protos")
    def test_improve_vocabulary_item_google_api_error(self, mock_protos, mock_model_class, mock_configure):
        """Test vocabulary improvement with Google API call error."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = google.api_core.exceptions.GoogleAPICallError("API error")
        mock_model_class.return_value = mock_model

        client = GeminiClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "Gemini API call failed" in str(exc_info.value) and "API error" in str(exc_info.value)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.protos")
    def test_improve_vocabulary_item_general_exception(self, mock_protos, mock_model_class, mock_configure):
        """Test vocabulary improvement with general exception."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = ValueError("Some other error")
        mock_model_class.return_value = mock_model

        client = GeminiClient(api_key=self.api_key)

        with pytest.raises(LLMError) as exc_info:
            client.improve_vocabulary_item(self.prompt)

        assert "Vocabulary improvement failed: Some other error" in str(exc_info.value)
