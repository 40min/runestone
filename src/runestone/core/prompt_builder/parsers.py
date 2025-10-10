"""
Response parsers for LLM outputs.

This module provides unified parsing and validation for all LLM response types,
including fallback strategies for malformed responses.
"""

import json
import re
from typing import Any, Dict, Optional

from .exceptions import ResponseParseError
from .types import ImprovementMode
from .validators import AnalysisResponse, OCRResponse, VocabularyResponse


class ResponseParser:
    """
    Unified response parser for all LLM output types.

    Provides JSON parsing with automatic fallback strategies for
    malformed responses, and Pydantic validation for type safety.
    """

    def __init__(self):
        """Initialize the response parser."""
        pass

    def parse_ocr_response(self, response: str) -> OCRResponse:
        """
        Parse OCR response with validation.

        Args:
            response: Raw LLM response string

        Returns:
            Validated OCRResponse object

        Raises:
            ResponseParseError: If parsing and fallback both fail

        Example:
            >>> parser = ResponseParser()
            >>> result = parser.parse_ocr_response(llm_response)
            >>> print(result.transcribed_text)
        """
        try:
            data = self._parse_json(response)

            # Check for error response
            if "error" in data:
                raise ResponseParseError(data["error"])

            return OCRResponse(**data)
        except Exception as e:
            raise ResponseParseError(f"Failed to parse OCR response: {str(e)}")

    def parse_analysis_response(self, response: str) -> AnalysisResponse:
        """
        Parse content analysis response with automatic fallback.

        Args:
            response: Raw LLM response string

        Returns:
            Validated AnalysisResponse object

        Raises:
            ResponseParseError: If parsing and fallback both fail

        Example:
            >>> parser = ResponseParser()
            >>> result = parser.parse_analysis_response(llm_response)
            >>> print(result.grammar_focus.topic)
        """
        try:
            data = self._parse_json(response)
            return AnalysisResponse(**data)
        except Exception as e:
            # Try fallback parsing
            try:
                fallback_data = self._fallback_analysis_parse(response)
                return AnalysisResponse(**fallback_data)
            except Exception as fallback_error:
                raise ResponseParseError(
                    f"Failed to parse analysis response: {str(e)}. Fallback also failed: {str(fallback_error)}"
                )

    def parse_search_response(self, response: str) -> str:
        """
        Parse search response (returns as plain text).

        Search responses are expected to be structured text, not JSON,
        so this method simply returns the cleaned response.

        Args:
            response: Raw LLM response string

        Returns:
            Cleaned response text

        Example:
            >>> parser = ResponseParser()
            >>> text = parser.parse_search_response(llm_response)
        """
        return response.strip()

    def parse_vocabulary_response(self, response: str, mode: ImprovementMode) -> VocabularyResponse:
        """
        Parse vocabulary improvement response based on mode.

        Args:
            response: Raw LLM response string
            mode: Improvement mode that was requested

        Returns:
            Validated VocabularyResponse object with fields populated based on mode

        Raises:
            ResponseParseError: If parsing and fallback both fail

        Example:
            >>> parser = ResponseParser()
            >>> result = parser.parse_vocabulary_response(
            ...     llm_response,
            ...     ImprovementMode.ALL_FIELDS
            ... )
            >>> print(result.translation)
        """
        try:
            data = self._parse_json(response)
        except json.JSONDecodeError:
            # Try fallback parsing for malformed responses
            data = self._fallback_vocabulary_parse(response, mode)

        # Filter fields based on mode
        filtered_data = self._filter_vocabulary_by_mode(data, mode)

        return VocabularyResponse(**filtered_data)

    def _parse_json(self, response: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from response, handling markdown code blocks.

        Args:
            response: Raw response string that may contain JSON

        Returns:
            Parsed JSON as dictionary

        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        # Clean and extract JSON
        cleaned = self._extract_json(response)
        return json.loads(cleaned)

    def _extract_json(self, response: str) -> str:
        """
        Extract JSON from markdown code blocks or other formatting.

        Handles patterns like:
        - ```json {...} ```
        - ``` {...} ```
        - Plain JSON text

        Args:
            response: Raw response text

        Returns:
            Extracted JSON string
        """
        response = response.strip()

        # Try to extract from markdown code blocks
        code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(code_block_pattern, response, re.DOTALL)
        if match:
            return match.group(1)

        # If no code block, assume the whole response is JSON
        # Remove any leading/trailing whitespace
        return response

    def _fallback_analysis_parse(self, response: str) -> Dict[str, Any]:
        """
        Fallback parser for malformed analysis responses.

        Returns a minimal valid analysis structure when JSON parsing fails.

        Args:
            response: Raw response text

        Returns:
            Dictionary with basic analysis structure
        """
        return {
            "grammar_focus": {
                "has_explicit_rules": False,
                "topic": "Swedish language practice",
                "explanation": "This page contains Swedish language exercises and examples.",
                "rules": None,
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
        }

    def _fallback_vocabulary_parse(self, response_text: str, mode: ImprovementMode) -> Dict[str, Any]:
        """
        Parse a malformed vocabulary response using regex and heuristics.

        This is extracted from VocabularyService._parse_malformed_llm_response()
        and attempts to extract information from various malformed formats.

        Args:
            response_text: Raw response text
            mode: Improvement mode

        Returns:
            Dictionary with extracted vocabulary data
        """
        result: Dict[str, Optional[str]] = {"translation": None, "example_phrase": "", "extra_info": None}

        response_text = response_text.strip()

        # Try to find JSON-like structure even if malformed
        if response_text.startswith("{") and response_text.endswith("}"):
            # Try to fix common JSON issues
            fixed_text = response_text
            # Fix trailing commas
            fixed_text = re.sub(r",(\s*[}\]])", r"\1", fixed_text)
            # Fix missing quotes around keys
            fixed_text = re.sub(r"(\w+):", r'"\1":', fixed_text)
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass  # Continue with regex extraction

        # Try to extract using regex patterns
        translation_match = re.search(r'(?:"translation"|\btranslation)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
        if translation_match:
            result["translation"] = translation_match.group(1)

        example_match = re.search(
            r'(?:"example_phrase"|\bexample_phrase)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE
        )
        if example_match:
            result["example_phrase"] = example_match.group(1)

        extra_info_match = re.search(r'(?:"extra_info"|\bextra_info)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
        if extra_info_match:
            result["extra_info"] = extra_info_match.group(1)

        # If no structured data found, try to extract from plain text
        if not result["translation"] and not result["example_phrase"] and not result["extra_info"]:
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]
            if lines:
                # Assume the first line is the example phrase
                result["example_phrase"] = lines[0]

        # If translation was requested but not found, try to infer it
        if mode == ImprovementMode.ALL_FIELDS and not result["translation"]:
            words = re.findall(r"\b[a-zA-Z]+\b", response_text)
            # List of common English words to exclude
            common_words = {
                "the",
                "and",
                "for",
                "are",
                "but",
                "not",
                "you",
                "all",
                "can",
                "had",
                "her",
                "was",
                "one",
                "our",
                "out",
                "day",
                "get",
                "has",
                "him",
                "his",
                "how",
                "its",
                "may",
                "new",
                "now",
                "old",
                "see",
                "two",
                "way",
                "who",
                "boy",
                "did",
                "let",
                "put",
                "say",
                "she",
                "too",
                "use",
            }
            english_words = [w for w in words if len(w) > 2 and w.lower() not in common_words]
            if english_words:
                result["translation"] = " ".join(english_words[:3])

        return result

    def _filter_vocabulary_by_mode(self, data: Dict[str, Any], mode: ImprovementMode) -> Dict[str, Optional[str]]:
        """
        Filter vocabulary response data based on improvement mode.

        Args:
            data: Raw parsed data
            mode: Improvement mode

        Returns:
            Filtered dictionary with only requested fields
        """
        if mode == ImprovementMode.EXAMPLE_ONLY:
            return {
                "translation": None,
                "example_phrase": data.get("example_phrase", ""),
                "extra_info": None,
            }
        elif mode == ImprovementMode.EXTRA_INFO_ONLY:
            return {
                "translation": None,
                "example_phrase": None,
                "extra_info": data.get("extra_info"),
            }
        else:  # ALL_FIELDS
            return {
                "translation": data.get("translation"),
                "example_phrase": data.get("example_phrase", ""),
                "extra_info": data.get("extra_info"),
            }
