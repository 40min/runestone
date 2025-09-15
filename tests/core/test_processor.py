"""
Tests for the processor module.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.console import setup_console
from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor


class TestRunestoneProcessor:
    """Test cases for RunestoneProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        setup_console()
        self.settings = Settings()
        self.image_path = Path("test_image.jpg")

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_stateless_workflow_timing_logs(
        self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test that timing logs are generated for each step in stateless workflow."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result
        mock_ocr_result = {"text": "Sample Swedish text", "character_count": 20}
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False},
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer_instance.find_extra_learning_info.return_value = "Extra info"
        mock_analyzer.return_value = mock_analyzer_instance

        # Mock time.time to simulate durations
        time_values = [
            0.0,
            1.5,
            1.5,
            3.2,
            3.2,
            4.8,
        ]  # Start OCR, end OCR, start analysis, end analysis, start extra, end extra
        with patch("runestone.core.processor.time.time", side_effect=time_values):
            processor = RunestoneProcessor(settings=self.settings, verbose=True)

            # Test the stateless workflow
            ocr_result = processor.run_ocr(b"fake image data")
            analysis_result = processor.run_analysis(ocr_result["text"])
            resources_result = processor.run_resource_search(analysis_result)

        # Verify results
        assert ocr_result == mock_ocr_result
        assert analysis_result == mock_analysis
        assert resources_result == "Extra info"

        # Verify timing logs were called
        expected_calls = [
            ("OCR completed in 1.50 seconds",),
            ("Analysis completed in 1.70 seconds",),
            ("Resource search completed in 1.60 seconds",),
        ]

        # Check that logger.info was called with timing messages
        info_calls = [call for call in mock_logger.info.call_args_list if "completed in" in str(call)]
        assert len(info_calls) == 3

        # Verify the timing messages
        for i, call in enumerate(info_calls):
            args, kwargs = call
            message = args[0]
            assert "completed in" in message
            assert "seconds" in message

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_stateless_workflow_no_verbose_no_timing_logs(
        self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test that timing logs are not generated when verbose is False."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result
        mock_ocr_result = {"text": "Sample Swedish text", "character_count": 20}
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False},
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer_instance.find_extra_learning_info.return_value = ""
        mock_analyzer.return_value = mock_analyzer_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=False)

        # Test the stateless workflow
        ocr_result = processor.run_ocr(b"fake image data")
        analysis_result = processor.run_analysis(ocr_result["text"])
        resources_result = processor.run_resource_search(analysis_result)

        # Verify results
        assert ocr_result == mock_ocr_result
        assert analysis_result == mock_analysis
        assert resources_result == ""

        # Verify no timing logs were called (only other logs)
        timing_calls = [call for call in mock_logger.info.call_args_list if "completed in" in str(call)]
        assert len(timing_calls) == 0

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_stateless_workflow_exception_handling(
        self, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test exception handling in stateless workflow."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR to raise exception
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.side_effect = Exception("OCR failed")
        mock_ocr.return_value = mock_ocr_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=True)

        with pytest.raises(RunestoneError) as exc_info:
            processor.run_ocr(b"fake image data")

        assert "OCR processing failed" in str(exc_info.value)

        # Verify error was logged
        mock_logger.error.assert_called_once()

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_run_ocr_success(self, mock_formatter, mock_analyzer, mock_ocr, mock_image_open):
        """Test successful OCR processing."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock OCR result
        mock_ocr_result = {"text": "Sample Swedish text", "character_count": 20}
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=False)
        result = processor.run_ocr(b"fake image data")

        assert result == mock_ocr_result
        mock_ocr_instance.extract_text.assert_called_once()

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_run_analysis_success(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test successful content analysis."""
        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False},
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer.return_value = mock_analyzer_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=False)
        result = processor.run_analysis("Sample text")

        assert result == mock_analysis
        mock_analyzer_instance.analyze_content.assert_called_once_with("Sample text")

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_run_resource_search_success(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test successful resource search."""
        mock_resources = "Additional learning resources"
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.find_extra_learning_info.return_value = mock_resources
        mock_analyzer.return_value = mock_analyzer_instance

        mock_analysis_data = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": True},
        }

        processor = RunestoneProcessor(settings=self.settings, verbose=False)
        result = processor.run_resource_search(mock_analysis_data)

        assert result == mock_resources

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    @patch("builtins.open")
    def test_process_image_success(
        self, mock_open, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test successful image processing through complete workflow."""
        # Mock file reading with context manager
        mock_file = Mock()
        mock_file.read.return_value = b"fake image data"
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result
        mock_ocr_result = {"text": "Sample Swedish text", "character_count": 20}
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        # Mock analysis result
        mock_analysis = {
            "vocabulary": [{"swedish": "hej", "english": "hello"}],
            "grammar_focus": {"topic": "greetings"},
            "core_topics": ["greetings"],
            "search_needed": {"should_search": False},
        }
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_content.return_value = mock_analysis
        mock_analyzer_instance.find_extra_learning_info.return_value = "Extra info"
        mock_analyzer.return_value = mock_analyzer_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=True)
        result = processor.process_image(self.image_path)

        # Verify results structure
        assert "ocr_result" in result
        assert "analysis" in result
        assert "extra_info" in result
        assert result["ocr_result"] == mock_ocr_result
        assert result["analysis"] == mock_analysis
        assert result["extra_info"] == "Extra info"

        # Verify method calls
        mock_open.assert_called_once_with(self.image_path, "rb")
        mock_ocr_instance.extract_text.assert_called_once()
        mock_analyzer_instance.analyze_content.assert_called_once_with("Sample Swedish text")
        mock_analyzer_instance.find_extra_learning_info.assert_called_once_with(mock_analysis)

        # Verify logging
        mock_logger.info.assert_any_call(f"Starting processing of image: {self.image_path}")
        mock_logger.info.assert_any_call("Image processing completed successfully")

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    @patch("builtins.open")
    def test_process_image_no_text_extracted(
        self, mock_open, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test process_image when no text is extracted from image."""
        # Mock file reading with context manager
        mock_file = Mock()
        mock_file.read.return_value = b"fake image data"
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock OCR result with empty text
        mock_ocr_result = {"text": "", "character_count": 0}
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.return_value = mock_ocr_result
        mock_ocr.return_value = mock_ocr_instance

        processor = RunestoneProcessor(settings=self.settings, verbose=True)

        with pytest.raises(RunestoneError) as exc_info:
            processor.process_image(self.image_path)

        assert "No text extracted from image" in str(exc_info.value)

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.get_logger")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    @patch("builtins.open")
    def test_process_image_ocr_failure(
        self, mock_open, mock_formatter, mock_analyzer, mock_ocr, mock_get_logger, mock_image_open
    ):
        """Test process_image when OCR processing fails."""
        # Mock file reading with context manager
        mock_file = Mock()
        mock_file.read.return_value = b"fake image data"
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None

        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

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

        assert "OCR processing failed" in str(exc_info.value)
        assert mock_logger.error.call_count == 2
