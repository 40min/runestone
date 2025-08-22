"""
Main processor module that orchestrates the entire Runestone workflow.

This module coordinates OCR processing, content analysis, resource discovery,
and output formatting to provide a complete Swedish textbook analysis.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console

from .analyzer import ContentAnalyzer
from .clients.base import BaseLLMClient
from .clients.factory import create_llm_client
from .exceptions import RunestoneError
from .formatter import ResultFormatter
from .ocr import OCRProcessor


class RunestoneProcessor:
    """Main processor that orchestrates the complete Runestone workflow."""

    def __init__(
        self,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the Runestone processor.

        Args:
            client: Pre-configured LLM client (if provided, other params are ignored)
            provider: LLM provider name ("openai" or "gemini")
            api_key: API key for the provider
            model_name: Model name to use
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.console = Console()

        # Create or use provided client
        if client is not None:
            self.client = client
        else:
            self.client = create_llm_client(
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                verbose=verbose,
            )

        # Initialize components with the client
        try:
            self.ocr_processor = OCRProcessor(client=self.client, verbose=verbose)  # noqa: E501
            self.content_analyzer = ContentAnalyzer(client=self.client, verbose=verbose)
            self.formatter = ResultFormatter(self.console)
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
            self.console.print(f"[blue]Starting processing of:[/blue] {image_path}")

        try:
            # Step 1: Extract text using OCR
            if self.verbose:
                self.console.print("[blue]Step 1:[/blue] Extracting text from image...")

            ocr_result = self.ocr_processor.extract_text(image_path)

            if self.verbose:
                char_count = ocr_result.get("character_count", 0)
                self.console.print(f"[green]✓[/green] Extracted {char_count} characters")  # noqa: E501

            # Step 2: Analyze content
            if self.verbose:
                self.console.print("[blue]Step 2:[/blue] Analyzing content...")

            extracted_text = ocr_result.get("text", "")
            if not extracted_text:
                raise RunestoneError("No text was extracted from the image")

            analysis = self.content_analyzer.analyze_content(extracted_text)

            if self.verbose:
                vocab_count = len(analysis.get("vocabulary", []))
                self.console.print(f"[green]✓[/green] Found {vocab_count} vocabulary items")  # noqa: E501

            # Step 3: Find learning resources
            if self.verbose:
                self.console.print("[blue]Step 3:[/blue] Finding learning resources...")

            resources = self.content_analyzer.find_learning_resources(analysis)

            if self.verbose:
                resource_count = len(resources)
                self.console.print(f"[green]✓[/green] Found {resource_count} learning resources")  # noqa: E501

            # Compile complete results
            results = {
                "ocr_result": ocr_result,
                "analysis": analysis,
                "resources": resources,
                "processing_successful": True,
            }

            if self.verbose:
                self.console.print("[green]✓ Processing completed successfully![/green]")  # noqa: E501

            return results

        except Exception as e:
            if self.verbose:
                self.console.print(f"[red]✗ Processing failed:[/red] {str(e)}")

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
                resources=results["resources"],
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
                resources=results["resources"],
            )
            self.console.print(markdown_output)
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
                resources=results["resources"],
            )

            output_path.write_text(markdown_output, encoding="utf-8")

            if self.verbose:
                self.console.print(f"[green]✓[/green] Results saved to: {output_path}")  # noqa: E501

        except Exception as e:
            raise RunestoneError(f"Failed to save results to file: {str(e)}")
