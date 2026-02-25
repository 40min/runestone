"""
Content analysis module for Swedish textbook pages.

This module uses configurable LLM providers to analyze extracted text and identify
grammar rules, vocabulary, and generate learning resources.
"""

from typing import Optional

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import ContentAnalysisError
from runestone.core.logging_config import get_logger
from runestone.core.prompt_builder.builder import PromptBuilder
from runestone.core.prompt_builder.exceptions import ResponseParseError
from runestone.core.prompt_builder.parsers import ResponseParser
from runestone.schemas.analysis import ContentAnalysis


class ContentAnalyzer:
    """Analyzes Swedish textbook content using configurable LLM providers."""

    def __init__(
        self,
        settings: Settings,
        client: BaseLLMClient,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the content analyzer.

        Args:
            settings: Centralized application settings
            client: LLM client for processing
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        self.client = client

        # Initialize prompt builder and parser
        self.builder = PromptBuilder()
        self.parser = ResponseParser()

    def analyze_content(self, extracted_text: str) -> ContentAnalysis:
        """
        Analyze Swedish textbook content to extract learning materials.

        Args:
            extracted_text: Raw text extracted from the textbook page

        Returns:
            AnalysisResponse object containing analyzed content with grammar, vocabulary, and resources

        Raises:
            ContentAnalysisError: If content analysis fails
        """
        try:
            # Build analysis prompt using PromptBuilder
            analysis_prompt = self.builder.build_analysis_prompt(extracted_text)

            self.logger.debug(f"[ContentAnalyzer] Analyzing content with {self.client.provider_name}...")

            response_text = self.client.analyze_content(analysis_prompt)

            if not response_text:
                raise ContentAnalysisError("No analysis returned from LLM")

            # Log the raw response for debugging
            self.logger.debug(f"[ContentAnalyzer] Raw LLM response (first 500 chars): {response_text[:500]}")

            # Parse response using ResponseParser (includes automatic fallback)
            try:
                analysis_response = self.parser.parse_analysis_response(response_text)
                return analysis_response
            except ResponseParseError as e:
                self.logger.warning(f"[ContentAnalyzer] Response parsing failed: {e}")
                raise ContentAnalysisError(f"Failed to parse analysis response: {str(e)}")

        except ContentAnalysisError:
            raise
        except Exception as e:
            raise ContentAnalysisError(f"Content analysis failed: {str(e)}")
