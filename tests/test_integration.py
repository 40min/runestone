"""
Integration tests for Runestone.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from runestone.core.exceptions import RunestoneError
from runestone.core.processor import RunestoneProcessor


class TestRunestoneIntegration:
    """Integration tests for the complete Runestone workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.api_key = "test-api-key"
        self.test_image_path = Path("test_image.jpg")

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_processor_init_success(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test successful processor initialization."""
        processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None, verbose=True)

        assert processor.verbose is True
        # OCRProcessor and ContentAnalyzer are now called with client and verbose
        # Since we're mocking the classes at the module level, they should be called
        # when the processor initializes its components
        assert mock_ocr.called
        assert mock_analyzer.called
        mock_formatter.assert_called_once()

    @patch("runestone.core.processor.OCRProcessor")
    def test_processor_init_failure(self, mock_ocr):
        """Test processor initialization failure."""
        mock_ocr.side_effect = Exception("OCR init failed")

        with pytest.raises(RunestoneError) as exc_info:
            RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None)

        assert "Failed to initialize processor" in str(exc_info.value)

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_complete_workflow(self, mock_formatter, mock_analyzer, mock_ocr, mock_image_open):
        """Test complete image processing workflow."""
        # Create a temporary image file
        with self.runner.isolated_filesystem():
            self.test_image_path.touch()

            # Mock PIL Image
            mock_image = Mock()
            mock_image.size = (800, 600)
            mock_image_open.return_value = mock_image

            # Mock OCR results
            mock_ocr_result = {
                "text": "Hej, vad heter du?",
                "image_path": str(self.test_image_path),
                "image_size": (800, 600),
                "character_count": 17,
            }

            # Mock analysis results
            mock_analysis = {
                "grammar_focus": {
                    "has_explicit_rules": False,
                    "topic": "Swedish questions",
                    "explanation": "Basic question formation in Swedish",
                },
                "vocabulary": [
                    {"swedish": "hej", "english": "hello"},
                    {"swedish": "vad", "english": "what"},
                ],
                "core_topics": ["questions", "greetings"],
                "search_needed": {
                    "should_search": True,
                    "query_suggestions": ["Swedish questions"],
                },
            }

            # Mock resources
            mock_resources = [
                {
                    "title": "Swedish Questions Guide",
                    "url": "https://svenska.se/questions",
                    "description": "Guide to Swedish question formation",
                }
            ]

            # Configure mocks
            mock_ocr_instance = Mock()
            mock_ocr_instance.extract_text.return_value = mock_ocr_result
            mock_ocr.return_value = mock_ocr_instance

            mock_analyzer_instance = Mock()
            mock_analyzer_instance.analyze_content.return_value = mock_analysis
            mock_analyzer_instance.find_learning_resources.return_value = mock_resources
            mock_analyzer.return_value = mock_analyzer_instance

            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance

            # Run processor
            processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None, verbose=True)
            result = processor.process_image(self.test_image_path)

            # Verify workflow execution
            mock_ocr_instance.extract_text.assert_called_once_with(self.test_image_path)
            mock_analyzer_instance.analyze_content.assert_called_once_with("Hej, vad heter du?")
            mock_analyzer_instance.find_learning_resources.assert_called_once_with(mock_analysis)

            # Verify result structure
            assert result["processing_successful"] is True
            assert result["ocr_result"] == mock_ocr_result
            assert result["analysis"] == mock_analysis
            assert result["resources"] == mock_resources

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_ocr_failure(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test handling of OCR failure."""
        # Mock OCR failure
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text.side_effect = Exception("OCR failed")
        mock_ocr.return_value = mock_ocr_instance

        mock_analyzer.return_value = Mock()
        mock_formatter.return_value = Mock()

        processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None)

        with pytest.raises(RunestoneError) as exc_info:
            processor.process_image(self.test_image_path)

        assert "Processing failed" in str(exc_info.value)

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_process_image_empty_text(self, mock_formatter, mock_analyzer, mock_ocr, mock_image_open):
        """Test handling of empty extracted text."""
        # Create a temporary image file
        with self.runner.isolated_filesystem():
            self.test_image_path.touch()

            # Mock PIL Image
            mock_image = Mock()
            mock_image.size = (800, 600)
            mock_image_open.return_value = mock_image

            # Mock empty OCR result
            mock_ocr_result = {"text": "", "character_count": 0}

            mock_ocr_instance = Mock()
            mock_ocr_instance.extract_text.return_value = mock_ocr_result
            mock_ocr.return_value = mock_ocr_instance

            mock_analyzer.return_value = Mock()
            mock_formatter.return_value = Mock()

            processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None)

            with pytest.raises(RunestoneError) as exc_info:
                processor.process_image(self.test_image_path)

            assert "No text was extracted" in str(exc_info.value)

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_display_results_console(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test console result display."""
        mock_results = {
            "ocr_result": {"text": "test"},
            "analysis": {"grammar_focus": {}},
            "resources": [],
        }

        mock_ocr.return_value = Mock()
        mock_analyzer.return_value = Mock()

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None)
        processor.display_results_console(mock_results)

        mock_formatter_instance.format_console_output.assert_called_once_with(
            ocr_result=mock_results["ocr_result"],
            analysis=mock_results["analysis"],
            resources=mock_results["resources"],
        )

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_display_results_markdown(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test markdown result display."""
        mock_results = {
            "ocr_result": {"text": "test"},
            "analysis": {"grammar_focus": {}},
            "resources": [],
        }

        mock_ocr.return_value = Mock()
        mock_analyzer.return_value = Mock()

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown_output.return_value = "# Markdown Output"
        mock_formatter.return_value = mock_formatter_instance

        processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None)
        processor.display_results_markdown(mock_results)

        mock_formatter_instance.format_markdown_output.assert_called_once_with(
            ocr_result=mock_results["ocr_result"],
            analysis=mock_results["analysis"],
            resources=mock_results["resources"],
        )

    @patch("runestone.core.processor.OCRProcessor")
    @patch("runestone.core.processor.ContentAnalyzer")
    @patch("runestone.core.processor.ResultFormatter")
    def test_save_results_to_file(self, mock_formatter, mock_analyzer, mock_ocr):
        """Test saving results to file."""
        mock_results = {
            "ocr_result": {"text": "test"},
            "analysis": {"grammar_focus": {}},
            "resources": [],
        }

        mock_ocr.return_value = Mock()
        mock_analyzer.return_value = Mock()

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown_output.return_value = "# Markdown Output"
        mock_formatter.return_value = mock_formatter_instance

        # Mock Path.write_text
        output_path = Mock()

        processor = RunestoneProcessor(provider="openai", api_key=self.api_key, model_name=None, verbose=True)
        processor.save_results_to_file(mock_results, output_path)

        mock_formatter_instance.format_markdown_output.assert_called_once()
        output_path.write_text.assert_called_once_with("# Markdown Output", encoding="utf-8")
