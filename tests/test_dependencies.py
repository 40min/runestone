"""
Tests for dependency injection providers.

This module tests the dependency injection functions in dependencies.py,
ensuring they create and return the correct instances with proper dependencies.
"""

from unittest.mock import Mock, patch

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.clients.base import BaseLLMClient
from runestone.core.ocr import OCRProcessor
from runestone.core.processor import RunestoneProcessor
from runestone.dependencies import (
    get_content_analyzer,
    get_llm_client,
    get_ocr_processor,
    get_runestone_processor,
    get_vocabulary_service,
)
from runestone.services.vocabulary_service import VocabularyService


class TestDependencyProviders:
    """Test cases for dependency injection providers."""

    @patch("runestone.dependencies.create_llm_client")
    def test_get_llm_client(self, mock_create_client):
        """Test get_llm_client provider creates client correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.llm_model_name = "gpt-4"

        mock_client = Mock(spec=BaseLLMClient)
        mock_create_client.return_value = mock_client

        # Execute
        result = get_llm_client(mock_settings)

        # Assert
        assert result == mock_client
        mock_create_client.assert_called_once_with(
            settings=mock_settings,
            provider="openai",
            api_key="test-key",
            model_name="gpt-4",
        )

    @patch("runestone.dependencies.ContentAnalyzer")
    def test_get_content_analyzer(self, mock_content_analyzer_class):
        """Test get_content_analyzer provider creates analyzer correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_llm_client = Mock(spec=BaseLLMClient)
        mock_analyzer = Mock(spec=ContentAnalyzer)
        mock_content_analyzer_class.return_value = mock_analyzer

        # Execute
        result = get_content_analyzer(mock_settings, mock_llm_client)

        # Assert
        assert result == mock_analyzer
        mock_content_analyzer_class.assert_called_once_with(
            mock_settings,
            mock_llm_client,
        )

    @patch("runestone.dependencies.OCRProcessor")
    def test_get_ocr_processor(self, mock_ocr_processor_class):
        """Test get_ocr_processor provider creates processor correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_llm_client = Mock(spec=BaseLLMClient)
        mock_processor = Mock(spec=OCRProcessor)
        mock_ocr_processor_class.return_value = mock_processor

        # Execute
        result = get_ocr_processor(mock_settings, mock_llm_client)

        # Assert
        assert result == mock_processor
        mock_ocr_processor_class.assert_called_once_with(
            mock_settings,
            mock_llm_client,
        )

    @patch("runestone.dependencies.RunestoneProcessor")
    def test_get_runestone_processor(self, mock_runestone_processor_class):
        """Test get_runestone_processor provider creates processor correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_content_analyzer = Mock(spec=ContentAnalyzer)
        mock_processor = Mock(spec=RunestoneProcessor)
        mock_runestone_processor_class.return_value = mock_processor

        # Execute
        result = get_runestone_processor(mock_settings, mock_ocr_processor, mock_content_analyzer)

        # Assert
        assert result == mock_processor
        mock_runestone_processor_class.assert_called_once_with(
            mock_settings,
            mock_ocr_processor,
            mock_content_analyzer,
        )

    @patch("runestone.dependencies.VocabularyService")
    def test_get_vocabulary_service(self, mock_vocabulary_service_class):
        """Test get_vocabulary_service provider creates service correctly."""
        # Setup
        mock_repo = Mock()
        mock_settings = Mock(spec=Settings)
        mock_llm_client = Mock(spec=BaseLLMClient)
        mock_service = Mock(spec=VocabularyService)
        mock_vocabulary_service_class.return_value = mock_service

        # Execute
        result = get_vocabulary_service(mock_repo, mock_settings, mock_llm_client)

        # Assert
        assert result == mock_service
        mock_vocabulary_service_class.assert_called_once_with(
            mock_repo,
            mock_settings,
            mock_llm_client,
        )
