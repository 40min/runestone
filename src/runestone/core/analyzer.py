"""
Content analysis module for Swedish textbook pages.

This module uses configurable LLM providers to analyze extracted text and identify
grammar rules, vocabulary, and generate learning resources.
"""

import json
from typing import Any, Dict, List, Optional

from runestone.core import console
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.console import get_console
from runestone.core.exceptions import ContentAnalysisError
from runestone.core.prompts import ANALYSIS_PROMPT_TEMPLATE, SEARCH_PROMPT_TEMPLATE


class ContentAnalyzer:
    """Analyzes Swedish textbook content using configurable LLM providers."""

    def __init__(
        self,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the content analyzer.

        Args:
            client: Pre-configured LLM client (if provided, other params are ignored)
            provider: LLM provider name ("openai" or "gemini")
            api_key: API key for the provider
            model_name: Model name to use
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.console = get_console()

        if client is not None:
            self.client = client
        else:
            self.client = create_llm_client(
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                verbose=verbose,
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
                self.console.print(f"Analyzing content with {self.client.provider_name}...")

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

                if self.verbose:
                    self.console.print(f"Analysis completed - found {len(analysis.get('vocabulary', []))} vocabulary items")

                return analysis

            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract content manually
                if self.verbose:
                    self.console.print("[yellow]Warning:[/yellow] JSON parsing failed, attempting fallback analysis...")

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

    def find_learning_resources(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Find relevant learning resources using web search.

        Args:
            analysis: Content analysis results

        Returns:
            List of relevant learning resources with URLs
        """
        resources = []

        if not analysis.get("search_needed", {}).get("should_search", False):
            return resources

        try:
            # Get search queries from analysis
            search_queries = analysis.get("search_needed", {}).get("query_suggestions", [])
            core_topics = analysis.get("core_topics", [])

            if not search_queries and core_topics:
                # Generate search queries from topics
                search_queries = [f"Swedish {topic} grammar explanation" for topic in core_topics[:2]]

            if not search_queries:
                self.console.print("[yellow]Warning:[/yellow] No search queries generated")
                return resources

            # Perform searches using the LLM's search capability
            for query in search_queries[:2]:  # Limit to 2 searches
                if self.verbose:
                    self.console.print(f"Searching for resources: {query}")

                search_prompt = SEARCH_PROMPT_TEMPLATE.format(query=query)

                try:
                    response_text = self.client.search_resources(search_prompt)

                    if response_text and "http" in response_text:
                        # Extract URLs from the response (basic implementation)
                        lines = response_text.split("\n")
                        for line in lines:
                            if "http" in line and any(
                                domain in line
                                for domain in [
                                    "svenska.se",
                                    "clozemaster.com",
                                    "worddive.com",
                                    "kielibuusti.fi",
                                    "swedishpod101.com",
                                ]
                            ):
                                # Extract URL and title (simplified)
                                url_start = line.find("http")
                                url_end = line.find(" ", url_start)
                                if url_end == -1:
                                    url = line[url_start:].strip()
                                else:
                                    url = line[url_start:url_end].strip()

                                title = query.replace("Swedish ", "").title()
                                resources.append(
                                    {
                                        "title": f"Swedish {title} - Learning Resource",
                                        "url": url,
                                        "description": f"Educational resource for {query}",
                                    }
                                )

                                if len(resources) >= 3:
                                    break

                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]Warning:[/yellow] Search failed for query '{query}': {e}")
                    continue

            # If no resources found, provide default high-quality resources
            if not resources:
                resources = self._get_default_resources(analysis)

            return resources[:3]  # Return max 3 resources

        except Exception as e:
            if self.verbose:
                self.console.print(f"[red]Error:[/red] Resource search failed: {e}")
            return self._get_default_resources(analysis)

    def _get_default_resources(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Get default high-quality Swedish learning resources.

        Args:
            analysis: Content analysis results

        Returns:
            List of default learning resources
        """
        grammar_topic = analysis.get("grammar_focus", {}).get("topic", "grammar")

        return [
            {
                "title": "Svenska.se - Swedish Grammar Reference",
                "url": "https://svenska.se/tre/sprak/grammatik/",
                "description": "Official Swedish grammar reference and explanations",
            },
            {
                "title": "Swedish Grammar Basics - Clozemaster",
                "url": "https://www.clozemaster.com/blog/swedish-grammar/",
                "description": f"Comprehensive guide to Swedish {grammar_topic}",  # noqa: E501
            },
            {
                "title": "Swedish Language Learning - WordDive",
                "url": "https://worddive.com/en/grammar/swedish-grammar/",
                "description": "Interactive Swedish grammar lessons and exercises",  # noqa: E501
            },
        ]
