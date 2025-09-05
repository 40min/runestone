"""
Main processor module that orchestrates the entire Runestone workflow.

This module coordinates OCR processing, content analysis, resource discovery,
and output formatting to provide a complete Swedish textbook analysis.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.logging_config import get_logger
from runestone.core.exceptions import RunestoneError
from runestone.core.formatter import ResultFormatter
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

    def process_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Process a Swedish textbook page image end-to-end.

        Args:
            image_path: Path to the image file

        Returns:
            Complete processing results

        Raises:
            RunestoneError: If processing fails at any stage
        """
        if self.verbose:
            self.logger.info(f"Starting processing of: {image_path}")

        try:
            # Step 1: Extract text using OCR
            if self.verbose:
                self.logger.info("Step 1: Extracting text from image...")

            ocr_result = self.ocr_processor.extract_text(image_path)

            if self.verbose:
                char_count = ocr_result.get("character_count", 0)
                self.logger.info(f"Extracted {char_count} characters")  # noqa: E501

            # Step 2: Analyze content
            if self.verbose:
                self.logger.info("Step 2: Analyzing content...")

            extracted_text = ocr_result.get("text", "")
            if not extracted_text:
                raise RunestoneError("No text was extracted from the image")

            analysis = self.content_analyzer.analyze_content(extracted_text)

            if self.verbose:
                vocab_count = len(analysis.get("vocabulary", []))
                self.logger.info(f"Found {vocab_count} vocabulary items")  # noqa: E501

            # Step 3: Find learning extra learning info
            if self.verbose:
                self.logger.info("Step 3: Finding learning resources...")

            extra_info = self.content_analyzer.find_extra_learning_info(analysis)

            if self.verbose:
                if extra_info:
                    self.logger.info("Found extra learning information")
                else:
                    self.logger.warning("No extra learning information found")

            # Compile complete results
            results = {
                "ocr_result": ocr_result,
                "analysis": analysis,
                "extra_info": extra_info,
                "processing_successful": True,
            }

            if self.verbose:
                self.logger.info("Processing completed successfully!")  # noqa: E501

            return results

        except Exception as e:
            if self.verbose:
                self.logger.error(f"Processing failed: {str(e)}")

            if isinstance(e, RunestoneError):
                raise
            else:
                raise RunestoneError(f"Processing failed: {str(e)}")

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
