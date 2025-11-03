"""
Response parsers for LLM outputs.

This module provides unified parsing and validation for all LLM response types,
including fallback strategies for malformed responses.
"""

import json
import re
from typing import Any, Dict, Optional

from runestone.core.prompt_builder.exceptions import ResponseParseError
from runestone.core.prompt_builder.types import ImprovementMode
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem
from runestone.schemas.ocr import OCRResult, RecognitionStatistics
from runestone.schemas.vocabulary import VocabularyResponse


class ResponseParser:
    """
    Unified response parser for all LLM output types.

    Provides JSON parsing with automatic fallback strategies for
    malformed responses, and Pydantic validation for type safety.
    """

    def __init__(self):
        """Initialize the response parser."""
        pass

    def parse_ocr_response(self, response: str) -> OCRResult:
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

            return OCRResult(**data)
        except ResponseParseError:
            # Re-raise parse errors without attempting fallback
            raise
        except Exception as e:
            # Try fallback parsing for malformed responses
            try:
                return self._fallback_ocr_parse(response)
            except Exception as fallback_error:
                raise ResponseParseError(
                    f"Failed to parse OCR response: {str(e)}. Fallback also failed: {str(fallback_error)}"
                )

    def parse_analysis_response(self, response: str) -> ContentAnalysis:
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
            return ContentAnalysis(**data)
        except Exception as e:
            # Try fallback parsing
            try:
                return self._fallback_analysis_parse(response)
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
            # Filter fields based on mode
            filtered_data = self._filter_vocabulary_by_mode(data, mode)
            return VocabularyResponse(**filtered_data)
        except json.JSONDecodeError:
            # Try fallback parsing for malformed responses
            return self._fallback_vocabulary_parse(response, mode)

    def parse_vocabulary_batch_response(self, response: str) -> Dict[str, Optional[str]]:
        """
        Parse batch vocabulary improvement response.

        Args:
            response: Raw LLM response string (expected as JSON dict)

        Returns:
            Dictionary mapping word_phrase -> extra_info (or None if failed)

        Raises:
            ResponseParseError: If parsing completely fails
        """
        try:
            data = self._parse_json(response)

            # Validate it's a dictionary
            if not isinstance(data, dict):
                raise ResponseParseError("Batch response must be a JSON object/dictionary")

            # Normalize: ensure all values are str or None
            result = {}
            for word_phrase, extra_info in data.items():
                if extra_info is None or isinstance(extra_info, str):
                    result[word_phrase] = extra_info
                else:
                    # Convert to string if possible
                    result[word_phrase] = str(extra_info) if extra_info else None

            return result

        except json.JSONDecodeError:
            # Try fallback parsing
            return self._fallback_vocabulary_batch_parse(response)

    def _fallback_vocabulary_batch_parse(self, response: str) -> Dict[str, Optional[str]]:
        """
        Fallback parser for malformed batch responses.

        Attempts to extract key-value pairs using regex when JSON parsing fails.
        """
        result = {}

        # Try to find quoted key-value pairs
        # Pattern: "key": "value" or "key": null
        pattern = r'"([^"]+)"\s*:\s*(?:"([^"]*)"|null)'
        matches = re.finditer(pattern, response, re.DOTALL)

        for match in matches:
            word_phrase = match.group(1)
            extra_info = match.group(2) if match.group(2) else None
            result[word_phrase] = extra_info

        if not result:
            raise ResponseParseError("Could not extract any vocabulary data from malformed batch response")

        return result

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

    def _fallback_ocr_parse(self, response: str) -> OCRResult:
        """
        Fallback parser for malformed OCR responses.

        Attempts to extract transcribed text and recognition statistics from
        malformed responses using regex and heuristics.

        Args:
            response: Raw response text

        Returns:
            OCRResult object with OCR data structure

        Raises:
            ResponseParseError: If no meaningful text can be extracted
        """
        response = response.strip()
        transcribed_text = ""
        total_elements = 0
        successfully_transcribed = 0
        unclear_uncertain = 0
        unable_to_recognize = 0

        # Try to find JSON-like structure even if malformed
        if response.startswith("{") and response.endswith("}"):
            # Try to fix common JSON issues
            fixed_text = response
            # Fix trailing commas
            fixed_text = re.sub(r",(\s*[}\]])", r"\1", fixed_text)
            # Fix missing quotes around keys
            fixed_text = re.sub(r"(\w+):", r'"\1":', fixed_text)
            try:
                data = json.loads(fixed_text)
                return OCRResult(**data)
            except (json.JSONDecodeError, Exception):
                pass  # Continue with regex extraction

        # Try to extract transcribed_text field
        transcribed_match = re.search(
            r'(?:"transcribed_text"|transcribed_text)\s*:\s*"([^"]*)"', response, re.DOTALL | re.IGNORECASE
        )
        if transcribed_match:
            transcribed_text = transcribed_match.group(1)

        # Try to extract recognition statistics
        total_match = re.search(r'(?:"total_elements"|total_elements)\s*:\s*(\d+)', response, re.IGNORECASE)
        if total_match:
            total_elements = int(total_match.group(1))

        success_match = re.search(
            r'(?:"successfully_transcribed"|successfully_transcribed)\s*:\s*(\d+)', response, re.IGNORECASE
        )
        if success_match:
            successfully_transcribed = int(success_match.group(1))

        unclear_match = re.search(r'(?:"unclear_uncertain"|unclear_uncertain)\s*:\s*(\d+)', response, re.IGNORECASE)
        if unclear_match:
            unclear_uncertain = int(unclear_match.group(1))

        unable_match = re.search(r'(?:"unable_to_recognize"|unable_to_recognize)\s*:\s*(\d+)', response, re.IGNORECASE)
        if unable_match:
            unable_to_recognize = int(unable_match.group(1))

        # If no transcribed text found, try to extract plain text
        if not transcribed_text:
            # Remove JSON-like structure markers
            text = re.sub(r'[{}"\[\]]', "", response)
            # Remove field names
            field_pattern = (
                r"(transcribed_text|recognition_statistics|total_elements|"
                r"successfully_transcribed|unclear_uncertain|unable_to_recognize)\s*:\s*"
            )
            text = re.sub(field_pattern, "", text, flags=re.IGNORECASE)
            # Clean up and get first reasonable text block
            lines = [line.strip() for line in text.split("\n") if line.strip() and not line.strip().isdigit()]
            if lines:
                transcribed_text = "\n".join(lines[:10])  # Take first 10 meaningful lines

        # If still no text extracted, raise an error
        if not transcribed_text:
            raise ResponseParseError("Could not extract transcribed text from malformed OCR response")

        return OCRResult(
            transcribed_text=transcribed_text,
            recognition_statistics=RecognitionStatistics(
                total_elements=total_elements,
                successfully_transcribed=successfully_transcribed,
                unclear_uncertain=unclear_uncertain,
                unable_to_recognize=unable_to_recognize,
            ),
        )

    def _fallback_analysis_parse(self, response: str) -> ContentAnalysis:
        """
        Fallback parser for malformed analysis responses.

        Attempts to extract analysis components from malformed responses
        using regex and heuristics.

        Args:
            response: Raw response text

        Returns:
            AnalysisResponse object with analysis structure

        Raises:
            ResponseParseError: If no meaningful data can be extracted
        """
        response = response.strip()

        # Initialize with default values
        has_explicit_rules = False
        topic = ""
        explanation = ""
        rules = None
        vocabulary = []
        core_topics = []
        should_search = True
        query_suggestions = []

        # Try to find JSON-like structure even if malformed
        if response.startswith("{") and response.endswith("}"):
            # Try to fix common JSON issues
            fixed_text = response
            # Fix trailing commas
            fixed_text = re.sub(r",(\s*[}\]])", r"\1", fixed_text)
            # Fix missing quotes around keys
            fixed_text = re.sub(r"(\w+):", r'"\1":', fixed_text)
            try:
                parsed_json = json.loads(fixed_text)
                return ContentAnalysis(**parsed_json)
            except (json.JSONDecodeError, Exception):
                pass  # Continue with regex extraction

        # Try to extract grammar_focus fields
        topic_match = re.search(r'(?:"topic"|topic)\s*:\s*"([^"]*)"', response, re.IGNORECASE)
        if topic_match:
            topic = topic_match.group(1)

        explanation_match = re.search(r'(?:"explanation"|explanation)\s*:\s*"([^"]*)"', response, re.IGNORECASE)
        if explanation_match:
            explanation = explanation_match.group(1)

        rules_match = re.search(r'(?:"rules"|rules)\s*:\s*"([^"]*)"', response, re.IGNORECASE)
        if rules_match:
            rules = rules_match.group(1)

        has_rules_match = re.search(
            r'(?:"has_explicit_rules"|has_explicit_rules)\s*:\s*(true|false)', response, re.IGNORECASE
        )
        if has_rules_match:
            has_explicit_rules = has_rules_match.group(1).lower() == "true"

        # Try to extract vocabulary items
        vocab_pattern = (
            r'\{\s*"swedish"\s*:\s*"([^"]*)"\s*,\s*"english"\s*:\s*"([^"]*)"\s*'
            r'(?:,\s*"example_phrase"\s*:\s*(?:"([^"]*)"|null))?\s*\}'
        )
        vocab_matches = re.finditer(vocab_pattern, response, re.IGNORECASE)
        for match in vocab_matches:
            vocabulary.append(
                VocabularyItem(
                    swedish=match.group(1),
                    english=match.group(2),
                    example_phrase=match.group(3) if match.group(3) else None,
                )
            )

        # Try to extract core_topics
        topics_match = re.search(r'(?:"core_topics"|core_topics)\s*:\s*\[(.*?)\]', response, re.DOTALL | re.IGNORECASE)
        if topics_match:
            topics_str = topics_match.group(1)
            core_topics = re.findall(r'"([^"]*)"', topics_str)

        # Try to extract search_needed
        should_search_match = re.search(
            r'(?:"should_search"|should_search)\s*:\s*(true|false)', response, re.IGNORECASE
        )
        if should_search_match:
            should_search = should_search_match.group(1).lower() == "true"

        queries_match = re.search(
            r'(?:"query_suggestions"|query_suggestions)\s*:\s*\[(.*?)\]', response, re.DOTALL | re.IGNORECASE
        )
        if queries_match:
            queries_str = queries_match.group(1)
            query_suggestions = re.findall(r'"([^"]*)"', queries_str)

        # Ensure all required fields have default values if missing
        if not topic:
            topic = "Swedish language practice"

        if not explanation:
            explanation = "Could not extract complete explanation from response"

        if not core_topics:
            core_topics = ["Swedish language learning"]

        if not query_suggestions:
            query_suggestions = ["Swedish grammar basics", "Swedish vocabulary practice"]

        # If absolutely no meaningful data was extracted, raise error
        if (
            (not topic or topic == "Swedish language practice")
            and not vocabulary
            and len(core_topics) == 1
            and core_topics[0] == "Swedish language learning"
        ):
            # Try to extract any text content as a last resort
            lines = [line.strip() for line in response.split("\n") if line.strip()]
            if not lines:
                raise ResponseParseError("Could not extract meaningful analysis data from malformed response")

        return ContentAnalysis(
            grammar_focus=GrammarFocus(
                has_explicit_rules=has_explicit_rules,
                topic=topic,
                explanation=explanation,
                rules=rules,
            ),
            vocabulary=vocabulary,
            core_topics=core_topics,
            search_needed=SearchNeeded(
                should_search=should_search,
                query_suggestions=query_suggestions,
            ),
        )

    def _fallback_vocabulary_parse(self, response_text: str, mode: ImprovementMode) -> VocabularyResponse:
        """
        Parse a malformed vocabulary response using regex and heuristics.

        This is extracted from VocabularyService._parse_malformed_llm_response()
        and attempts to extract information from various malformed formats.

        Args:
            response_text: Raw response text
            mode: Improvement mode

        Returns:
            VocabularyResponse object with extracted vocabulary data
        """
        translation = None
        example_phrase = ""
        extra_info = None

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
                data = json.loads(fixed_text)
                filtered_data = self._filter_vocabulary_by_mode(data, mode)
                return VocabularyResponse(**filtered_data)
            except (json.JSONDecodeError, Exception):
                pass  # Continue with regex extraction

        # Try to extract using regex patterns
        translation_match = re.search(r'(?:"translation"|\btranslation)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
        if translation_match:
            translation = translation_match.group(1)

        example_match = re.search(
            r'(?:"example_phrase"|\bexample_phrase)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE
        )
        if example_match:
            example_phrase = example_match.group(1)

        extra_info_match = re.search(r'(?:"extra_info"|\bextra_info)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
        if extra_info_match:
            extra_info = extra_info_match.group(1)

        # If no structured data found, try to extract from plain text
        if not translation and not example_phrase and not extra_info:
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]
            if lines:
                # Assume the first line is the example phrase
                example_phrase = lines[0]

        # If translation was requested but not found, try to infer it
        if mode == ImprovementMode.ALL_FIELDS and not translation:
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
                translation = " ".join(english_words[:3])

        # Filter fields based on mode
        if mode == ImprovementMode.EXAMPLE_ONLY:
            return VocabularyResponse(translation=None, example_phrase=example_phrase, extra_info=None)
        elif mode == ImprovementMode.EXTRA_INFO_ONLY:
            return VocabularyResponse(translation=None, example_phrase=None, extra_info=extra_info)
        else:  # ALL_FIELDS
            return VocabularyResponse(translation=translation, example_phrase=example_phrase, extra_info=extra_info)

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
