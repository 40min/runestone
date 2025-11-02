"""
Integration tests for Runestone.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.console import setup_console
from runestone.core.exceptions import RunestoneError
from runestone.core.ocr import OCRProcessor
from runestone.core.processor import RunestoneProcessor
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem
from runestone.schemas.ocr import OCRResult, RecognitionStatistics
from runestone.services.vocabulary_service import VocabularyService


class TestRunestoneIntegration:
    """Integration tests for the complete Runestone workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        setup_console()
        self.runner = CliRunner()
        self.api_key = "test-api-key"
        self.test_image_path = Path("test_image.jpg")
        self.settings = Settings()

    @patch("runestone.core.processor.ResultFormatter")
    def test_processor_init_success(self, mock_formatter):
        """Test successful processor initialization."""
        mock_ocr = Mock(spec=OCRProcessor)
        mock_analyzer = Mock(spec=ContentAnalyzer)

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr,
            content_analyzer=mock_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
            verbose=True,
        )

        assert processor.verbose is True
        assert processor.ocr_processor == mock_ocr
        assert processor.content_analyzer == mock_analyzer
        mock_formatter.assert_called_once()

    def test_processor_init_failure(self):
        """Test processor initialization failure."""
        with pytest.raises(RunestoneError) as exc_info:
            RunestoneProcessor(
                settings=self.settings,
                ocr_processor=None,
                content_analyzer=None,
                vocabulary_service=Mock(spec=VocabularyService),
            )

        assert "Failed to initialize processor" in str(exc_info.value)

    @patch("PIL.Image.open")
    @patch("runestone.core.processor.ResultFormatter")
    def test_stateless_workflow_complete(self, mock_formatter, mock_image_open):
        """Test complete stateless processing workflow."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock OCR results
        mock_ocr_result = OCRResult(
            transcribed_text="Hej, vad heter du?",
            recognition_statistics=RecognitionStatistics(
                total_elements=17,
                successfully_transcribed=17,
                unclear_uncertain=0,
                unable_to_recognize=0,
            ),
        )

        # Mock analysis results
        mock_analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(
                has_explicit_rules=False,
                topic="Swedish questions",
                explanation="Basic question formation in Swedish",
                rules=None,
            ),
            vocabulary=[
                VocabularyItem(swedish="hej", english="hello", example_phrase=None),
                VocabularyItem(swedish="vad", english="what", example_phrase=None),
            ],
            core_topics=["questions", "greetings"],
            search_needed=SearchNeeded(
                should_search=True,
                query_suggestions=["Swedish questions"],
            ),
        )

        # Mock resources
        mock_resources = "Additional learning resources about Swedish questions"

        # Configure mocks
        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_ocr_processor.extract_text.return_value = mock_ocr_result

        mock_content_analyzer = Mock(spec=ContentAnalyzer)
        mock_content_analyzer.analyze_content.return_value = mock_analysis
        mock_content_analyzer.find_extra_learning_info.return_value = mock_resources

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        # Run processor with new stateless workflow
        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
            verbose=True,
        )

        # Simulate the workflow step by step
        image_bytes = b"fake image data"
        ocr_result = processor.run_ocr(image_bytes)
        analysis_result = processor.run_analysis(ocr_result.transcribed_text)
        resources_result = processor.run_resource_search(analysis_result.core_topics, analysis_result.search_needed)

        # Verify workflow execution
        mock_ocr_processor.extract_text.assert_called_once()
        mock_content_analyzer.analyze_content.assert_called_once_with("Hej, vad heter du?")
        mock_content_analyzer.find_extra_learning_info.assert_called_once_with(
            mock_analysis.core_topics, mock_analysis.search_needed
        )

        # Verify result structure
        assert ocr_result == mock_ocr_result
        assert analysis_result == mock_analysis
        assert resources_result == mock_resources

    @patch("PIL.Image.open")
    def test_process_image_ocr_failure(self, mock_image_open):
        """Test handling of OCR failure."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock OCR failure
        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_ocr_processor.extract_text.side_effect = Exception("OCR failed")

        mock_content_analyzer = Mock(spec=ContentAnalyzer)

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
        )

        with pytest.raises(RunestoneError) as exc_info:
            processor.run_ocr(b"fake image data")

        assert "OCR processing failed" in str(exc_info.value)

    @patch("PIL.Image.open")
    def test_process_image_empty_text(self, mock_image_open):
        """Test handling of empty extracted text."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        # Mock empty OCR result
        mock_ocr_result = OCRResult(
            transcribed_text="",
            recognition_statistics=RecognitionStatistics(
                total_elements=0,
                successfully_transcribed=0,
                unclear_uncertain=0,
                unable_to_recognize=0,
            ),
        )

        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_ocr_processor.extract_text.return_value = mock_ocr_result

        mock_content_analyzer = Mock(spec=ContentAnalyzer)

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
        )

        with pytest.raises(RunestoneError) as exc_info:
            ocr_result = processor.run_ocr(b"fake image data")
            processor.run_analysis(ocr_result.transcribed_text)

        assert "No text provided for analysis" in str(exc_info.value)

    @patch("runestone.core.processor.ResultFormatter")
    def test_display_results_console(self, mock_formatter):
        """Test console result display."""
        mock_ocr_result = OCRResult(
            transcribed_text="test",
            recognition_statistics=RecognitionStatistics(
                total_elements=4,
                successfully_transcribed=4,
                unclear_uncertain=0,
                unable_to_recognize=0,
            ),
        )
        mock_analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(has_explicit_rules=False, topic="", explanation="", rules=None),
            vocabulary=[],
            core_topics=[],
            search_needed=SearchNeeded(should_search=False, query_suggestions=[]),
        )
        mock_results = {
            "ocr_result": mock_ocr_result,
            "analysis": mock_analysis,
            "extra_info": "",
        }

        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_content_analyzer = Mock(spec=ContentAnalyzer)

        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
        )
        processor.display_results_console(mock_results)

        mock_formatter_instance.format_console_output.assert_called_once_with(
            ocr_result=mock_results["ocr_result"],
            analysis=mock_results["analysis"],
            extra_info=mock_results["extra_info"],
        )

    @patch("runestone.core.processor.ResultFormatter")
    def test_display_results_markdown(self, mock_formatter):
        """Test markdown result display."""
        mock_ocr_result = OCRResult(
            transcribed_text="test",
            recognition_statistics=RecognitionStatistics(
                total_elements=4,
                successfully_transcribed=4,
                unclear_uncertain=0,
                unable_to_recognize=0,
            ),
        )
        mock_analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(has_explicit_rules=False, topic="", explanation="", rules=None),
            vocabulary=[],
            core_topics=[],
            search_needed=SearchNeeded(should_search=False, query_suggestions=[]),
        )
        mock_results = {
            "ocr_result": mock_ocr_result,
            "analysis": mock_analysis,
            "extra_info": "",
        }

        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_content_analyzer = Mock(spec=ContentAnalyzer)

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown_output.return_value = "# Markdown Output"
        mock_formatter.return_value = mock_formatter_instance

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
        )
        processor.display_results_markdown(mock_results)

        mock_formatter_instance.format_markdown_output.assert_called_once_with(
            ocr_result=mock_results["ocr_result"],
            analysis=mock_results["analysis"],
            resources=mock_results["extra_info"],
        )

    @patch("runestone.core.processor.ResultFormatter")
    def test_save_results_to_file(self, mock_formatter):
        """Test saving results to file."""
        mock_results = {
            "ocr_result": {"text": "test"},
            "analysis": {"grammar_focus": {}},
            "extra_info": "",
        }

        mock_ocr_processor = Mock(spec=OCRProcessor)
        mock_content_analyzer = Mock(spec=ContentAnalyzer)

        mock_formatter_instance = Mock()
        mock_formatter_instance.format_markdown_output.return_value = "# Markdown Output"
        mock_formatter.return_value = mock_formatter_instance

        # Mock Path.write_text
        output_path = Mock()

        processor = RunestoneProcessor(
            settings=self.settings,
            ocr_processor=mock_ocr_processor,
            content_analyzer=mock_content_analyzer,
            vocabulary_service=Mock(spec=VocabularyService),
            verbose=True,
        )
        processor.save_results_to_file(mock_results, output_path)

        mock_formatter_instance.format_markdown_output.assert_called_once_with(
            ocr_result=mock_results["ocr_result"],
            analysis=mock_results["analysis"],
            resources=mock_results["extra_info"],
        )
        output_path.write_text.assert_called_once_with("# Markdown Output", encoding="utf-8")
