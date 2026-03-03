"""
Tests for the OpenAI client module updated for AsyncOpenAI SDK.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from PIL import Image

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import LLMError


class TestOpenAIClient:
    """Test cases for OpenAIClient class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.prompt = "test prompt"

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_extract_text_from_image_success(self, mock_openai_class):
        """Test successful OCR extraction."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Extracted text from image which is long enough"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        mock_image = Image.new("RGB", (10, 10))

        result = await client.extract_text_from_image(mock_image, "ocr prompt")

        assert result == "Extracted text from image which is long enough"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_analyze_content_success(self, mock_openai_class):
        """Test successful content analysis."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Analysis result"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        result = await client.analyze_content("analyze prompt")

        assert result == "Analysis result"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_search_resources_success(self, mock_openai_class):
        """Test successful resource search."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Search results"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        result = await client.search_resources("search prompt")

        assert result == "Search results"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_success(self, mock_openai_class):
        """Test successful vocabulary improvement."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Improved vocabulary data"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        result = await client.improve_vocabulary_item(self.prompt)

        assert result == "Improved vocabulary data"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_no_response(self, mock_openai_class):
        """Test vocabulary improvement with no response text."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content=None))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_item(self.prompt)

        assert f"No vocabulary improvement returned from {client.provider_name}" in str(exc_info.value)

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_item_api_error(self, mock_openai_class):
        """Test vocabulary improvement with OpenAI API error."""
        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")

        client = OpenAIClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_item(self.prompt)

        assert "Vocabulary improvement failed (Exception): OpenAI API Error" in str(exc_info.value)

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_batch_success(self, mock_openai_class):
        """Test successful vocabulary batch improvement."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="Batch improved data"))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        result = await client.improve_vocabulary_batch(self.prompt)

        assert result == "Batch improved data"
        mock_client.chat.completions.create.assert_called_once()

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_batch_no_response(self, mock_openai_class):
        """Test vocabulary batch improvement with no response text."""
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content=None))]

        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        client = OpenAIClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_batch(self.prompt)

        assert f"No vocabulary batch improvement returned from {client.provider_name}" in str(exc_info.value)

    @patch("runestone.core.clients.openai_client.AsyncOpenAI")
    async def test_improve_vocabulary_batch_api_error(self, mock_openai_class):
        """Test vocabulary batch improvement with OpenAI API error."""
        mock_client = mock_openai_class.return_value
        mock_client.chat.completions.create.side_effect = Exception("Batch API Error")

        client = OpenAIClient(api_key=self.api_key)
        with pytest.raises(LLMError) as exc_info:
            await client.improve_vocabulary_batch(self.prompt)

        assert "Vocabulary batch improvement failed (Exception): Batch API Error" in str(exc_info.value)
