"""
Main processor module that orchestrates the entire Runestone workflow.

This module coordinates OCR processing, content analysis, resource discovery,
and output formatting to provide a complete Swedish textbook analysis.
"""

import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.exceptions import RunestoneError
from runestone.core.formatter import ResultFormatter
from runestone.core.logging_config import get_logger
from runestone.core.ocr import OCRProcessor
from runestone.core.prompt_builder.validators import AnalysisResponse, OCRResponse
from runestone.services.vocabulary_service import VocabularyService


class RunestoneProcessor:
    """Main processor that orchestrates the complete Runestone workflow."""

    def __init__(
        self,
        settings: Settings,
        ocr_processor: OCRProcessor,
        content_analyzer: ContentAnalyzer,
        vocabulary_service: VocabularyService,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the Runestone processor.

        Args:
            settings: Centralized application settings
            ocr_processor: OCR processor instance
            content_analyzer: Content analyzer instance
            verbose: Enable verbose logging. If None, uses settings.verbose
            vocabulary_service: Vocabulary service for marking known words
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        # Initialize components
        try:
            if ocr_processor is None:
                raise RunestoneError("OCR processor cannot be None")
            if content_analyzer is None:
                raise RunestoneError("Content analyzer cannot be None")

            self.ocr_processor = ocr_processor
            self.content_analyzer = content_analyzer
            self.formatter = ResultFormatter()
            self.vocabulary_service = vocabulary_service
        except Exception as e:
            raise RunestoneError(f"Failed to initialize processor: {str(e)}")

    def run_ocr(self, image_bytes: bytes) -> OCRResponse:
        """
        Run OCR on image bytes.

        Args:
            image_bytes: Raw image bytes

        Returns:
            OCR result object

        Raises:
            RunestoneError: If OCR processing fails
        """
        try:
            self.logger.debug(f"[RunestoneProcessor] Starting OCR, received {len(image_bytes)} bytes")

            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))

            self.logger.debug(f"[RunestoneProcessor] Image loaded: mode={image.mode}, size={image.size}")

            start_time = time.time()
            ocr_result = self.ocr_processor.extract_text(image)
            duration = time.time() - start_time

            char_count = ocr_result.recognition_statistics.total_elements
            self.logger.debug(
                f"[RunestoneProcessor] OCR completed in {duration:.2f} seconds, extracted {char_count} characters"
            )

            return ocr_result

        except Exception as e:
            self.logger.error(f"[RunestoneProcessor] OCR processing failed: {type(e).__name__}: {str(e)}")
            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"OCR processing failed: {type(e).__name__}: {str(e)}")

    def run_analysis(self, text: str, user_id: int = 1) -> AnalysisResponse:
        """
        Analyze extracted text content and mark known vocabulary.

        Args:
            text: Extracted text from OCR
            user_id: User ID for checking known vocabulary (default: 1)

        Returns:
            Content analysis results with known vocabulary marked

        Raises:
            RunestoneError: If content analysis fails
        """
        try:
            if not text:
                raise RunestoneError("No text provided for analysis")

            self.logger.debug("[RunestoneProcessor] Analyzing content...")

            start_time = time.time()
            analysis = self.content_analyzer.analyze_content(text)
            duration = time.time() - start_time

            vocab_count = len(analysis.vocabulary)
            self.logger.debug(
                f"[RunestoneProcessor] Analysis completed in {duration:.2f} seconds, "
                f"found {vocab_count} vocabulary items"
            )

            # Mark known vocabulary if vocabulary_service is available
            if analysis.vocabulary:
                self._mark_known_vocabulary(analysis, user_id)

            return analysis

        except Exception as e:
            self.logger.error(f"[RunestoneProcessor] Content analysis failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"Content analysis failed: {str(e)}")

    def _mark_known_vocabulary(self, analysis: AnalysisResponse, user_id: int = 1) -> None:
        """
        Mark vocabulary items as known if they exist in the user's database.

        Args:
            analysis: Analysis response containing vocabulary items
            user_id: User ID for checking known vocabulary
        """
        try:
            # Extract Swedish words from vocabulary
            swedish_words = [item.swedish for item in analysis.vocabulary]

            # Get known words from database
            known_words = self.vocabulary_service.get_existing_word_phrases(swedish_words, user_id)

            # Mark vocabulary items as known
            known_count = 0
            for item in analysis.vocabulary:
                if item.swedish in known_words:
                    item.known = True
                    known_count += 1

            self.logger.debug(
                f"[RunestoneProcessor] Marked {known_count}/{len(analysis.vocabulary)} vocabulary items as known"
            )

        except Exception as e:
            # Log error but don't fail the entire analysis
            self.logger.warning(f"[RunestoneProcessor] Failed to mark known vocabulary: {str(e)}")

    def run_resource_search(self, analysis_data: AnalysisResponse) -> str:
        """
        Find extra learning resources based on analysis.

        Args:
            analysis_data: Content analysis results

        Returns:
            Extra learning information as string

        Raises:
            RunestoneError: If resource search fails
        """
        try:
            self.logger.debug("[RunestoneProcessor] Searching for learning resources...")

            start_time = time.time()
            extra_info = self.content_analyzer.find_extra_learning_info(analysis_data)
            duration = time.time() - start_time

            if extra_info:
                self.logger.debug(f"[RunestoneProcessor] Resource search completed in {duration:.2f} seconds")
            else:
                self.logger.warning(
                    f"[RunestoneProcessor] Resource search completed in {duration:.2f} seconds, no results found"
                )

            return extra_info

        except Exception as e:
            self.logger.error(f"[RunestoneProcessor] Resource search failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"Resource search failed: {str(e)}")

    def display_results_console(self, results: Dict[str, Any]) -> None:
        """
        Display processing results to console using Rich formatting. # noqa: E501

        Args:
            results: Complete processing results from process_image()
        """
        try:
            self.formatter.format_console_output(
                ocr_result=results["ocr_result"],
                analysis=results["analysis"],
                extra_info=results["extra_info"],
            )
        except Exception as e:
            raise RunestoneError(f"Failed to display results: {str(e)}")

    def display_results_markdown(self, results: Dict[str, Any]) -> None:
        """
        Display processing results as markdown output. # noqa: E501

        Args:
            results: Complete processing results from process_image()
        """
        try:
            markdown_output = self.formatter.format_markdown_output(
                ocr_result=results["ocr_result"],
                analysis=results["analysis"],
                resources=results["extra_info"],
            )
            print(markdown_output)
        except Exception as e:
            raise RunestoneError(f"Failed to generate markdown output: {str(e)}")

    def process_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Process an image file through the complete Runestone workflow.

        Args:
            image_path: Path to the image file to process

        Returns:
            Complete processing results dictionary with ocr_result, analysis, and extra_info

        Raises:
            RunestoneError: If processing fails at any step
        """
        try:
            self.logger.debug(f"[RunestoneProcessor] Starting processing of image: {image_path}")

            # Read image file
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Step 1: OCR processing
            ocr_result = self.run_ocr(image_bytes)

            # Extract text for analysis
            extracted_text = ocr_result.transcribed_text
            if not extracted_text:
                raise RunestoneError("No text extracted from image")

            # Step 2: Content analysis
            analysis = self.run_analysis(extracted_text)

            # Step 3: Resource search
            extra_info = self.run_resource_search(analysis)

            # Combine results
            results = {
                "ocr_result": ocr_result,
                "analysis": analysis,
                "extra_info": extra_info,
            }

            self.logger.debug("[RunestoneProcessor] Image processing completed successfully")

            return results

        except Exception as e:
            self.logger.error(f"[RunestoneProcessor] Image processing failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"Image processing failed: {str(e)}")

    def save_results_to_file(self, results: Dict[str, Any], output_path: Path) -> None:
        """
        Save processing results to a markdown file. # noqa: E501

        Args:
            results: Complete processing results from process_image()
            output_path: Path where to save the markdown file
        """
        try:
            markdown_output = self.formatter.format_markdown_output(
                ocr_result=results["ocr_result"],
                analysis=results["analysis"],
                resources=results["extra_info"],
            )

            output_path.write_text(markdown_output, encoding="utf-8")

            self.logger.debug(f"[RunestoneProcessor] Results saved to: {output_path}")  # noqa: E501

        except Exception as e:
            raise RunestoneError(f"Failed to save results to file: {str(e)}")
