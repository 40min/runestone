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
from runestone.core.prompt_builder.validators import AnalysisResponse


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

    def analyze_content(self, extracted_text: str) -> AnalysisResponse:
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

            if self.verbose:
                self.logger.info(f"Analyzing content with {self.client.provider_name}...")

            response_text = self.client.analyze_content(analysis_prompt)

            if not response_text:
                raise ContentAnalysisError("No analysis returned from LLM")

            # Log the raw response for debugging
            if self.verbose:
                self.logger.debug(f"Raw LLM response (first 500 chars): {response_text[:500]}")

            # Parse response using ResponseParser (includes automatic fallback)
            try:
                analysis_response = self.parser.parse_analysis_response(response_text)
                return analysis_response
            except ResponseParseError as e:
                if self.verbose:
                    self.logger.warning(f"Response parsing failed: {e}")
                raise ContentAnalysisError(f"Failed to parse analysis response: {str(e)}")

        except ContentAnalysisError:
            raise
        except Exception as e:
            raise ContentAnalysisError(f"Content analysis failed: {str(e)}")

    def find_extra_learning_info(self, analysis: AnalysisResponse) -> str:
        """
        Find extra learning information using web search and compile educational material.

        Args:
            analysis: Content analysis results

        Returns:
            Compiled educational material from web search as a string
        """
        if not analysis.search_needed.should_search:
            return ""

        try:
            # Get search queries and core topics from analysis
            search_queries = analysis.search_needed.query_suggestions
            core_topics = analysis.core_topics

            if not search_queries and not core_topics:
                self.logger.warning("No search queries or topics generated")
                return ""

            if self.verbose:
                self.logger.info(
                    f"Searching for educational material on topics: {core_topics} and queries: {search_queries}"
                )

            # Build search prompt using PromptBuilder
            search_prompt = self.builder.build_search_prompt(
                core_topics=core_topics[:3], query_suggestions=search_queries[:4]
            )

            try:
                response_text = self.client.search_resources(search_prompt)

                if response_text:
                    # Parse search response (returns as plain text)
                    return self.parser.parse_search_response(response_text)

                # Fallback with simple message if no response
                return "No extra learning info available at this time."

            except Exception as e:
                if self.verbose:
                    self.logger.warning(f"Search failed: {e}")
                return f"Search failed: {str(e)}"

        except Exception as e:
            if self.verbose:
                self.logger.error(f"Resource search failed: {e}")
            return f"Resource search failed: {str(e)}"
