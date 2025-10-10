"""
Content analysis module for Swedish textbook pages.

This module uses configurable LLM providers to analyze extracted text and identify
grammar rules, vocabulary, and generate learning resources.
"""

from typing import Any, Dict, Optional

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import ContentAnalysisError
from runestone.core.logging_config import get_logger
from runestone.core.prompt_builder import PromptBuilder, ResponseParser
from runestone.core.prompt_builder.exceptions import ResponseParseError


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

    def analyze_content(self, extracted_text: str) -> Dict[str, Any]:
        """
        Analyze Swedish textbook content to extract learning materials.

        Args:
            extracted_text: Raw text extracted from the textbook page

        Returns:
            Dictionary containing analyzed content with grammar, vocabulary, and resources

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

            # Parse response using ResponseParser (includes automatic fallback)
            try:
                analysis_response = self.parser.parse_analysis_response(response_text)

                # Convert to dictionary format for backward compatibility
                return {
                    "grammar_focus": {
                        "has_explicit_rules": analysis_response.grammar_focus.has_explicit_rules,
                        "topic": analysis_response.grammar_focus.topic,
                        "explanation": analysis_response.grammar_focus.explanation,
                        "rules": analysis_response.grammar_focus.rules,
                    },
                    "vocabulary": [
                        {
                            "swedish": item.swedish,
                            "english": item.english,
                            "example_phrase": item.example_phrase,
                        }
                        for item in analysis_response.vocabulary
                    ],
                    "core_topics": analysis_response.core_topics,
                    "search_needed": {
                        "should_search": analysis_response.search_needed.should_search,
                        "query_suggestions": analysis_response.search_needed.query_suggestions,
                    },
                }
            except ResponseParseError as e:
                if self.verbose:
                    self.logger.warning(f"Response parsing failed: {e}")
                raise ContentAnalysisError(f"Failed to parse analysis response: {str(e)}")

        except ContentAnalysisError:
            raise
        except Exception as e:
            raise ContentAnalysisError(f"Content analysis failed: {str(e)}")

    def find_extra_learning_info(self, analysis: Dict[str, Any]) -> str:
        """
        Find extra learning information using web search and compile educational material.

        Args:
            analysis: Content analysis results

        Returns:
            Compiled educational material from web search as a string
        """
        if not analysis.get("search_needed", {}).get("should_search", False):
            return ""

        try:
            # Get search queries and core topics from analysis
            search_queries = analysis.get("search_needed", {}).get("query_suggestions", [])
            core_topics = analysis.get("core_topics", [])

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
