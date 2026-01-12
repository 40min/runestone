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
    get_ocr_llm_client,
    get_ocr_processor,
    get_runestone_processor,
    get_vocabulary_service,
)
from runestone.services.vocabulary_service import VocabularyService


class TestDependencyProviders:
    """Test cases for dependency injection providers."""

    def test_get_llm_client(self):
        """Test get_llm_client access from app state."""
        mock_request = Mock()
        expected_client = Mock(spec=BaseLLMClient)
        mock_request.app.state.llm_client = expected_client

        result = get_llm_client(mock_request)

        assert result == expected_client

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

    def test_get_ocr_llm_client(self):
        """Test get_ocr_llm_client access from app state."""
        mock_request = Mock()
        expected_client = Mock(spec=BaseLLMClient)
        mock_request.app.state.ocr_llm_client = expected_client

        result = get_ocr_llm_client(mock_request)

        assert result == expected_client

    @patch("runestone.dependencies.OCRProcessor")
    def test_get_ocr_processor(self, mock_ocr_processor_class):
        """Test get_ocr_processor provider creates processor with OCR client correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_ocr_llm_client = Mock(spec=BaseLLMClient)
        mock_processor = Mock(spec=OCRProcessor)
        mock_ocr_processor_class.return_value = mock_processor

        # Execute
        result = get_ocr_processor(mock_settings, mock_ocr_llm_client)

        # Assert
        assert result == mock_processor
        mock_ocr_processor_class.assert_called_once_with(
            mock_settings,
            mock_ocr_llm_client,
        )

    @patch("runestone.dependencies.RunestoneProcessor")
    def test_get_runestone_processor(self, mock_runestone_processor_class):
        """Test get_runestone_processor provider creates processor correctly."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_content_analyzer = Mock(spec=ContentAnalyzer)
        mock_vocabulary_service = Mock(spec=VocabularyService)
        mock_processor = Mock(spec=RunestoneProcessor)
        mock_runestone_processor_class.return_value = mock_processor

        # Execute
        mock_user_repo = Mock()
        result = get_runestone_processor(
            mock_settings, mock_ocr_processor, mock_content_analyzer, mock_vocabulary_service, mock_user_repo
        )

        # Assert
        assert result == mock_processor
        mock_runestone_processor_class.assert_called_once_with(
            mock_settings,
            mock_ocr_processor,
            mock_content_analyzer,
            mock_vocabulary_service,
            mock_user_repo,
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
