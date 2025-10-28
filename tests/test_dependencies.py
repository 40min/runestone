"""
Tests for dependency injection providers.

This module tests the dependency injection functions in dependencies.py,
ensuring they create and return the correct instances with proper dependencies.
"""

from unittest.mock import Mock, patch

import pytest

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

    @pytest.mark.parametrize(
        "provider, key_attr, key_value",
        [
            ("openai", "openai_api_key", "openai-test-key"),
            ("openrouter", "openrouter_api_key", "openrouter-test-key"),
        ],
    )
    @patch("runestone.dependencies.create_llm_client")
    def test_get_llm_client(self, mock_create_client, provider, key_attr, key_value):
        """Test get_llm_client provider creates client correctly for all providers."""
        mock_settings = Mock(spec=Settings, llm_provider=provider, llm_model_name="test-model")
        setattr(mock_settings, key_attr, key_value)

        get_llm_client(mock_settings)

        mock_create_client.assert_called_once_with(settings=mock_settings)

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

    @patch("runestone.dependencies.create_llm_client")
    def test_get_ocr_llm_client_with_dedicated_provider(self, mock_create_client):
        """Test get_ocr_llm_client creates dedicated client when ocr_llm_provider is set."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_settings.ocr_llm_provider = "openrouter"
        mock_settings.ocr_llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_main_client = Mock(spec=BaseLLMClient)
        mock_ocr_client = Mock(spec=BaseLLMClient)
        mock_create_client.return_value = mock_ocr_client

        # Execute
        result = get_ocr_llm_client(mock_settings, mock_main_client)

        # Assert - should create a new dedicated client
        assert result == mock_ocr_client
        assert result is not mock_main_client  # Verify it's a different instance
        mock_create_client.assert_called_once_with(
            settings=mock_settings,
            provider="openrouter",
            model_name="anthropic/claude-3.5-sonnet",
        )

    def test_get_ocr_llm_client_fallback_to_main(self):
        """Test get_ocr_llm_client returns main client when ocr_llm_provider is not set."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_settings.ocr_llm_provider = None  # Not configured
        mock_main_client = Mock(spec=BaseLLMClient)

        # Execute
        result = get_ocr_llm_client(mock_settings, mock_main_client)

        # Assert - should return the same main client instance (fallback)
        assert result is mock_main_client

    @patch("runestone.dependencies.create_llm_client")
    def test_get_ocr_llm_client_passes_correct_parameters(self, mock_create_client):
        """Test get_ocr_llm_client passes correct provider and model_name."""
        # Setup
        mock_settings = Mock(spec=Settings)
        mock_settings.ocr_llm_provider = "openrouter"
        mock_settings.ocr_llm_model_name = "anthropic/claude-3.5-sonnet"
        mock_main_client = Mock(spec=BaseLLMClient)
        mock_ocr_client = Mock(spec=BaseLLMClient)
        mock_create_client.return_value = mock_ocr_client

        # Execute
        result = get_ocr_llm_client(mock_settings, mock_main_client)

        # Assert
        assert result == mock_ocr_client
        mock_create_client.assert_called_once_with(
            settings=mock_settings,
            provider="openrouter",
            model_name="anthropic/claude-3.5-sonnet",
        )

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
