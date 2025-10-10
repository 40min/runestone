"""
Tests for response parsers with fallback strategies.
"""

import pytest

from runestone.core.prompt_builder.exceptions import ResponseParseError
from runestone.core.prompt_builder.parsers import ResponseParser
from runestone.core.prompt_builder.types import ImprovementMode


class TestResponseParserFallbacks:
    """Test cases for parser fallback strategies."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ResponseParser()

    # OCR Fallback Tests
    def test_fallback_ocr_parse_with_partial_json(self):
        """Test OCR fallback parser with partially valid JSON."""
        malformed_response = """
        {
            "transcribed_text": "Hej! Hur mår du?",
            "recognition_statistics": {
                total_elements: 50,
                successfully_transcribed: 45,
                "unclear_uncertain": 3,
                "unable_to_recognize": 2
            }
        }
        """

        result = self.parser._fallback_ocr_parse(malformed_response)

        assert "transcribed_text" in result
        assert "recognition_statistics" in result
        assert result["transcribed_text"] == "Hej! Hur mår du?"
        assert result["recognition_statistics"]["total_elements"] == 50
        assert result["recognition_statistics"]["successfully_transcribed"] == 45

    def test_fallback_ocr_parse_with_text_only(self):
        """Test OCR fallback parser with plain text response."""
        plain_text_response = """
        Some transcribed text from the image.
        This is the second line.
        And a third line.
        """

        result = self.parser._fallback_ocr_parse(plain_text_response)

        assert "transcribed_text" in result
        assert len(result["transcribed_text"]) > 0
        assert "Some transcribed text" in result["transcribed_text"]

    def test_fallback_ocr_parse_empty_response_raises_error(self):
        """Test OCR fallback parser raises error on empty response."""
        with pytest.raises(ResponseParseError) as exc_info:
            self.parser._fallback_ocr_parse("")

        assert "Could not extract transcribed text" in str(exc_info.value)

    def test_fallback_ocr_parse_with_broken_json(self):
        """Test OCR fallback parser with completely broken JSON."""
        broken_response = 'transcribed_text: "Hej världen!", total_elements: 10'

        result = self.parser._fallback_ocr_parse(broken_response)

        assert "transcribed_text" in result
        assert result["transcribed_text"] == "Hej världen!"
        assert result["recognition_statistics"]["total_elements"] == 10

    # Analysis Fallback Tests
    def test_fallback_analysis_parse_with_partial_json(self):
        """Test analysis fallback parser with partially valid JSON."""
        malformed_response = """
        {
            "grammar_focus": {
                has_explicit_rules: true,
                "topic": "Swedish possessives",
                "explanation": "Rules for possessive pronouns in Swedish"
            },
            "vocabulary": [
                {"swedish": "min", "english": "my"},
                {swedish: "din", english: "your"}
            ],
            "core_topics": ["possessives", "pronouns"],
        }
        """

        result = self.parser._fallback_analysis_parse(malformed_response)

        assert "grammar_focus" in result
        assert result["grammar_focus"]["topic"] == "Swedish possessives"
        assert result["grammar_focus"]["explanation"] == "Rules for possessive pronouns in Swedish"
        assert result["grammar_focus"]["has_explicit_rules"] is True
        assert len(result["vocabulary"]) >= 1

    def test_fallback_analysis_parse_extracts_vocab_items(self):
        """Test analysis fallback parser extracts vocabulary items."""
        response_with_vocab = """
        Some text with vocabulary:
        {"swedish": "hund", "english": "dog", "example_phrase": "Jag har en hund."}
        {"swedish": "katt", "english": "cat", "example_phrase": null}
        """

        result = self.parser._fallback_analysis_parse(response_with_vocab)

        assert len(result["vocabulary"]) == 2
        assert result["vocabulary"][0]["swedish"] == "hund"
        assert result["vocabulary"][0]["english"] == "dog"
        assert result["vocabulary"][1]["swedish"] == "katt"

    def test_fallback_analysis_parse_extracts_core_topics(self):
        """Test analysis fallback parser extracts core topics."""
        response_with_topics = """
        {
            "core_topics": ["Swedish grammar", "Verb conjugation", "Present tense"]
        }
        """

        result = self.parser._fallback_analysis_parse(response_with_topics)

        assert len(result["core_topics"]) == 3
        assert "Swedish grammar" in result["core_topics"]
        assert "Verb conjugation" in result["core_topics"]

    def test_fallback_analysis_parse_empty_response_raises_error(self):
        """Test analysis fallback parser raises error on completely empty response."""
        with pytest.raises(ResponseParseError) as exc_info:
            self.parser._fallback_analysis_parse("")

        assert "Could not extract meaningful analysis data" in str(exc_info.value)

    def test_fallback_analysis_parse_with_minimal_content(self):
        """Test analysis fallback parser with minimal content provides defaults."""
        minimal_response = "Some Swedish text about grammar"

        result = self.parser._fallback_analysis_parse(minimal_response)

        # Should provide default structure
        assert "grammar_focus" in result
        assert result["grammar_focus"]["topic"] == "Swedish language practice"
        assert len(result["core_topics"]) > 0

    # Vocabulary Fallback Tests (already exists but verify it works)
    def test_fallback_vocabulary_parse_with_broken_json(self):
        """Test vocabulary fallback parser with broken JSON."""
        malformed_response = 'translation: "apple", example_phrase: "Jag äter ett äpple.", extra_info: "en-word"'

        result = self.parser._fallback_vocabulary_parse(malformed_response, ImprovementMode.ALL_FIELDS)

        assert result["translation"] == "apple"
        assert result["example_phrase"] == "Jag äter ett äpple."
        assert result["extra_info"] == "en-word"

    # Integration Tests
    def test_parse_ocr_response_uses_fallback_on_error(self):
        """Test that parse_ocr_response uses fallback on JSON error."""
        malformed_response = 'transcribed_text: "Test text", total_elements: 5'

        # Should not raise error, should use fallback
        result = self.parser.parse_ocr_response(malformed_response)

        assert result.transcribed_text == "Test text"
        assert result.recognition_statistics.total_elements == 5

    def test_parse_analysis_response_uses_fallback_on_error(self):
        """Test that parse_analysis_response uses fallback on JSON error."""
        malformed_response = 'topic: "Swedish grammar", explanation: "Test explanation"'

        # Should not raise error, should use fallback
        result = self.parser.parse_analysis_response(malformed_response)

        assert result.grammar_focus.topic == "Swedish grammar"
        assert result.grammar_focus.explanation == "Test explanation"

    def test_parse_vocabulary_response_uses_fallback_on_error(self):
        """Test that parse_vocabulary_response uses fallback on JSON error."""
        malformed_response = 'translation: "test", example_phrase: "Ett test."'

        # Should not raise error, should use fallback
        result = self.parser.parse_vocabulary_response(malformed_response, ImprovementMode.ALL_FIELDS)

        assert result.translation == "test"
        assert result.example_phrase == "Ett test."

    def test_parse_ocr_response_raises_error_when_fallback_fails(self):
        """Test that parse_ocr_response raises error when both parsing and fallback fail."""
        completely_invalid = ""

        with pytest.raises(ResponseParseError) as exc_info:
            self.parser.parse_ocr_response(completely_invalid)

        assert "Failed to parse OCR response" in str(exc_info.value)
        assert "Fallback also failed" in str(exc_info.value)

    def test_parse_analysis_response_raises_error_when_fallback_fails(self):
        """Test that parse_analysis_response raises error when both parsing and fallback fail."""
        completely_invalid = ""

        with pytest.raises(ResponseParseError) as exc_info:
            self.parser.parse_analysis_response(completely_invalid)

        assert "Failed to parse analysis response" in str(exc_info.value)
        assert "Fallback also failed" in str(exc_info.value)
