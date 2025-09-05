"""
Content analysis module for Swedish textbook pages.

This module uses configurable LLM providers to analyze extracted text and identify
grammar rules, vocabulary, and generate learning resources.
"""

import json
from typing import Any, Dict, List, Optional

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.exceptions import ContentAnalysisError
from runestone.core.logging_config import get_logger
from runestone.core.prompts import ANALYSIS_PROMPT_TEMPLATE, SEARCH_PROMPT_TEMPLATE


class ContentAnalyzer:
    """Analyzes Swedish textbook content using configurable LLM providers."""

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
        Initialize the content analyzer.

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
            analysis_prompt = ANALYSIS_PROMPT_TEMPLATE.format(extracted_text=extracted_text)

            if self.verbose:
                self.logger.info(f"Analyzing content with {self.client.provider_name}...")

            response_text = self.client.analyze_content(analysis_prompt)

            if not response_text:
                raise ContentAnalysisError("No analysis returned from LLM")

            # Parse JSON response
            try:
                analysis = json.loads(response_text.strip())

                # Validate required fields
                required_fields = [
                    "grammar_focus",
                    "vocabulary",
                    "core_topics",
                    "search_needed",
                ]
                for field in required_fields:
                    if field not in analysis:
                        raise ContentAnalysisError(f"Missing required field: {field}")

                return analysis

            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract content manually
                if self.verbose:
                    self.logger.warning("JSON parsing failed, attempting fallback analysis...")

                return self._fallback_analysis(extracted_text, response_text)

        except ContentAnalysisError:
            raise
        except Exception as e:
            raise ContentAnalysisError(f"Content analysis failed: {str(e)}")

    def _fallback_analysis(self, extracted_text: str, raw_response: str) -> Dict[str, Any]:
        """
        Fallback analysis when JSON parsing fails.

        Args:
            extracted_text: Original extracted text
            raw_response: Raw LLM response

        Returns:
            Basic analysis structure
        """
        return {
            "grammar_focus": {
                "has_explicit_rules": False,
                "topic": "Swedish language practice",
                "explanation": "This page contains Swedish language exercises and examples.",  # noqa: E501
            },
            "vocabulary": [],
            "core_topics": ["Swedish language learning"],
            "search_needed": {
                "should_search": True,
                "query_suggestions": [
                    "Swedish grammar basics",
                    "Swedish vocabulary practice",
                ],
            },
            "fallback_used": True,
            "raw_response": raw_response,
        }

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
                self.logger.info(f"Searching for educational material on topics: {core_topics} and queries: {search_queries}")

            # Use combined queries in one search prompt
            search_prompt = SEARCH_PROMPT_TEMPLATE.format(
                core_topics=", ".join(f'"{topic}"' for topic in core_topics[:3]),
                query_suggestions=", ".join(f'"{query}"' for query in search_queries[:4]),
            )

            try:
                response_text = self.client.search_resources(search_prompt)

                if response_text:
                    # Return the LLM response as is
                    return response_text

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
