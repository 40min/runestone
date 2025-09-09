"""
Tests for the processor module.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.processor import RunestoneProcessor
from runestone.core.console import setup_console
from runestone.core.exceptions import RunestoneError


class TestRunestoneProcessor:
    """Test cases for RunestoneProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        setup_console()
        self.settings = Settings()
        self.image_path = Path("test_image.jpg")

    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_timing_logs(self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger):
        """Test that timing logs are generated for each step."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result
        mock_ocr_result = {
            "text": "Sample Swedish text",
            "character_count": 20
        }
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False}
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer_instance.find_extra_learning_info.return_value = "Extra info"
        mock_analyzer.return_value = mock_analyzer_instance

        # Mock time.time to simulate durations
        time_values = [0.0, 1.5, 1.5, 3.2, 3.2, 4.8]  # Start OCR, end OCR, start analysis, end analysis, start extra, end extra
        with patch("runestone.core.processor.time.time", side_effect=time_values):
            processor = RunestoneProcessor(settings=self.settings, verbose=True)
            result = processor.process_image(self.image_path)

        # Verify results
        assert result["processing_successful"] is True
        assert result["ocr_result"] == mock_ocr_result
        assert result["analysis"] == mock_analysis
        assert result["extra_info"] == "Extra info"

        # Verify timing logs were called
        expected_calls = [
            ("Step 1 took 1.50 seconds",),
            ("Step 2 took 1.70 seconds",),
            ("Step 3 took 1.60 seconds",)
        ]

        # Check that logger.info was called with timing messages
        info_calls = [call for call in mock_logger.info.call_args_list if "took" in str(call)]
        assert len(info_calls) == 3

        # Verify the timing messages
        for i, call in enumerate(info_calls):
            args, kwargs = call
            message = args[0]
            assert "Step" in message
            assert "took" in message
            assert "seconds" in message

    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_no_verbose_no_timing_logs(self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger):
        """Test that timing logs are not generated when verbose is False."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result
        mock_ocr_result = {
            "text": "Sample Swedish text",
            "character_count": 20
        }
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False}
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer_instance.find_extra_learning_info.return_value = ""
        mock_analyzer.return_value = mock_analyzer_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=False)
        result = processor.process_image(self.image_path)

        # Verify results
        assert result["processing_successful"] is True

        # Verify no timing logs were called (only other logs)
        timing_calls = [call for call in mock_logger.info.call_args_list if "took" in str(call)]
        assert len(timing_calls) == 0

    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_exception_handling(self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger):
        """Test exception handling in process_image."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR to raise exception
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.side_effect = Exception("OCR failed")
        mock_ocr.return_value = mock_ocr_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=True)

        with pytest.raises(RunestoneError) as exc_info:
            processor.process_image(self.image_path)

        assert "Processing failed" in str(exc_info.value)

        # Verify error was logged
        mock_logger.error.assert_called_once()