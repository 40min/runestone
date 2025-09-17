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
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.exceptions import RunestoneError
from runestone.core.formatter import ResultFormatter
from runestone.core.logging_config import get_logger
from runestone.core.ocr import OCRProcessor


class RunestoneProcessor:
    """Main processor that orchestrates the complete Runestone workflow."""

    def __init__(
        self,
        settings: Settings,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the Runestone processor.

        Args:
            settings: Centralized application settings
            client: Pre-configured LLM client (if provided, other params are ignored)
            provider: LLM provider name ("openai" or "gemini")
            api_key: API key for the provider
            model_name: Model name to use
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        # Create or use provided client
        if client is not None:
            self.client = client
        else:
            self.client = create_llm_client(
                settings=self.settings,
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                verbose=self.verbose,
            )

        # Initialize components with the client
        try:
            self.ocr_processor = OCRProcessor(settings=self.settings, client=self.client, verbose=self.verbose)
            self.content_analyzer = ContentAnalyzer(settings=self.settings, client=self.client, verbose=self.verbose)
            self.formatter = ResultFormatter()
        except Exception as e:
            raise RunestoneError(f"Failed to initialize processor: {str(e)}")

    def run_ocr(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Run OCR on image bytes.

        Args:
            image_bytes: Raw image bytes

        Returns:
            OCR result dictionary

        Raises:
            RunestoneError: If OCR processing fails
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))

            # Extract text using OCR
            if self.verbose:
                self.logger.info("Running OCR on image...")

            start_time = time.time()
            ocr_result = self.ocr_processor.extract_text(image)
            duration = time.time() - start_time

            if self.verbose:
                char_count = ocr_result.get("character_count", 0)
                self.logger.info(f"OCR completed in {duration:.2f} seconds, extracted {char_count} characters")

            return ocr_result

        except Exception as e:
            if self.verbose:
                self.logger.error(f"OCR processing failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"OCR processing failed: {str(e)}")

    def run_analysis(self, text: str) -> Dict[str, Any]:
        """
        Analyze extracted text content.

        Args:
            text: Extracted text from OCR

        Returns:
            Content analysis results

        Raises:
            RunestoneError: If content analysis fails
        """
        try:
            if not text:
                raise RunestoneError("No text provided for analysis")

            if self.verbose:
                self.logger.info("Analyzing content...")

            start_time = time.time()
            analysis = self.content_analyzer.analyze_content(text)
            duration = time.time() - start_time

            if self.verbose:
                vocab_count = len(analysis.get("vocabulary", []))
                self.logger.info(f"Analysis completed in {duration:.2f} seconds, found {vocab_count} vocabulary items")

            return analysis

        except Exception as e:
            if self.verbose:
                self.logger.error(f"Content analysis failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"Content analysis failed: {str(e)}")

    def run_resource_search(self, analysis_data: Dict[str, Any]) -> str:
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
            if self.verbose:
                self.logger.info("Searching for learning resources...")

            start_time = time.time()
            extra_info = self.content_analyzer.find_extra_learning_info(analysis_data)
            duration = time.time() - start_time

            if self.verbose:
                if extra_info:
                    self.logger.info(f"Resource search completed in {duration:.2f} seconds")
                else:
                    self.logger.warning(f"Resource search completed in {duration:.2f} seconds, no results found")

            return extra_info

        except Exception as e:
            if self.verbose:
                self.logger.error(f"Resource search failed: {str(e)}")

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
            if self.verbose:
                self.logger.info(f"Starting processing of image: {image_path}")

            # Read image file
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Step 1: OCR processing
            ocr_result = self.run_ocr(image_bytes)

            # Extract text for analysis
            extracted_text = ocr_result.get("text", "")
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

            if self.verbose:
                self.logger.info("Image processing completed successfully")

            return results

        except Exception as e:
            if self.verbose:
                self.logger.error(f"Image processing failed: {str(e)}")

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

            if self.verbose:
                self.logger.info(f"Results saved to: {output_path}")  # noqa: E501

        except Exception as e:
            raise RunestoneError(f"Failed to save results to file: {str(e)}")
