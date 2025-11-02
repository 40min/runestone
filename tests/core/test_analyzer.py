"""
Tests for the content analysis module.
"""

import json
from unittest.mock import Mock

import pytest

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.console import setup_console
from runestone.core.exceptions import ContentAnalysisError
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded, VocabularyItem


class TestContentAnalyzer:
    """Test cases for ContentAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        setup_console()
        self.api_key = "test-api-key"
        self.sample_text = "Hej, jag heter Anna. Hur mår du?"
        self.settings = Settings()

    def test_init_success(self):
        """Test successful initialization."""
        mock_client = Mock()
        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client, verbose=True)

        assert analyzer.client == mock_client
        assert analyzer.verbose is True

    def test_analyze_content_success(self):
        """Test successful content analysis."""
        # Mock analysis result
        analysis_result = ContentAnalysis(
            grammar_focus=GrammarFocus(
                has_explicit_rules=True,
                topic="Swedish greetings",
                explanation="Basic greeting patterns in Swedish",
                rules="Hej [hello] - greeting\nHur mår du? [how are you?] - question form",
            ),
            vocabulary=[
                VocabularyItem(swedish="hej", english="hello"),
                VocabularyItem(swedish="jag heter", english="my name is"),
            ],
            core_topics=["greetings", "introductions"],
            search_needed=SearchNeeded(
                should_search=True,
                query_suggestions=["Swedish greetings", "Swedish introductions"],
            ),
        )

        # Mock client response
        mock_response = analysis_result.model_dump_json()

        mock_client = Mock()
        mock_client.analyze_content.return_value = mock_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)
        result = analyzer.analyze_content(self.sample_text)

        # Verify result structure
        assert isinstance(result, ContentAnalysis)
        assert isinstance(result.grammar_focus, GrammarFocus)
        assert isinstance(result.vocabulary, list)
        assert isinstance(result.core_topics, list)
        assert isinstance(result.search_needed, SearchNeeded)

        # Verify specific content
        assert result.grammar_focus.topic == "Swedish greetings"
        assert result.grammar_focus.rules == "Hej [hello] - greeting\nHur mår du? [how are you?] - question form"
        assert len(result.vocabulary) == 2
        assert result.vocabulary[0].swedish == "hej"

        # Verify rules field is present
        assert hasattr(result.grammar_focus, "rules")

        # Verify client was called correctly
        mock_client.analyze_content.assert_called_once()
        args = mock_client.analyze_content.call_args[0]
        assert self.sample_text in args[0]
        assert "JSON format" in args[0]

    def test_analyze_content_invalid_json(self):
        """Test handling of invalid JSON response."""
        # Mock invalid JSON response
        mock_response = "This is not valid JSON"

        mock_client = Mock()
        mock_client.analyze_content.return_value = mock_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)
        result = analyzer.analyze_content(self.sample_text)

        # Should get fallback analysis with default structure
        assert isinstance(result, ContentAnalysis)
        assert isinstance(result.grammar_focus, GrammarFocus)
        assert isinstance(result.vocabulary, list)
        assert isinstance(result.core_topics, list)
        assert isinstance(result.search_needed, SearchNeeded)
        # Fallback provides minimal valid structure
        assert result.grammar_focus.topic == "Swedish language practice"
        assert isinstance(result.vocabulary, list)

    def test_analyze_content_missing_fields(self):
        """Test handling of JSON with missing required fields."""
        # Mock incomplete JSON response
        incomplete_result = {
            "grammar_focus": {
                "has_explicit_rules": True,
                "topic": "Swedish greetings",
                # Missing explanation
            }
            # Missing other required fields
        }

        mock_response = json.dumps(incomplete_result)

        mock_client = Mock()
        mock_client.analyze_content.return_value = mock_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)

        # With the new parser, missing fields trigger fallback
        result = analyzer.analyze_content(self.sample_text)

        # Should get fallback analysis that preserves extracted data and fills missing fields
        assert isinstance(result, ContentAnalysis)
        assert isinstance(result.grammar_focus, GrammarFocus)
        assert isinstance(result.vocabulary, list)
        # The topic from the partial JSON should be preserved
        assert result.grammar_focus.topic == "Swedish greetings"
        # Missing fields should be filled with defaults
        assert result.grammar_focus.explanation != ""
        assert isinstance(result.search_needed, SearchNeeded)

    def test_analyze_content_no_response(self):
        """Test handling of empty response."""
        mock_response = None

        mock_client = Mock()
        mock_client.analyze_content.return_value = mock_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)

        with pytest.raises(ContentAnalysisError) as exc_info:
            analyzer.analyze_content(self.sample_text)

        assert "No analysis returned" in str(exc_info.value)

    def test_find_extra_learning_info_no_search_needed(self):
        """Test resource finding when search is not needed."""
        analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(has_explicit_rules=False, topic="", explanation=""),
            vocabulary=[],
            core_topics=[],
            search_needed=SearchNeeded(should_search=False, query_suggestions=[]),
        )

        mock_client = Mock()
        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)
        resources = analyzer.find_extra_learning_info(analysis)

        assert resources == ""

    def test_find_extra_learning_info_with_search(self):
        """Test resource finding with search queries."""
        analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(has_explicit_rules=True, topic="Swedish greetings", explanation=""),
            vocabulary=[],
            core_topics=["greetings"],
            search_needed=SearchNeeded(should_search=True, query_suggestions=["Swedish greetings"]),
        )

        # Mock search response with educational material
        mock_search_response = (
            "Here is educational material about Swedish greetings and introductions. Swedish greetings include "
            "'Hej' (Hi), 'God morgon' (Good morning), and 'Tack' (Thank you). Use 'Jag heter' (My name is) "
            "followed by your name."
        )

        mock_client = Mock()
        mock_client.search_resources.return_value = mock_search_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)
        resources = analyzer.find_extra_learning_info(analysis)

        # Should return a string with educational material
        assert isinstance(resources, str)
        assert len(resources) > 0
        assert "Swedish greetings" in resources or "introductions" in resources

    def test_find_extra_learning_info_fallback(self):
        """Test fallback behavior when search fails."""
        analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(has_explicit_rules=True, topic="Swedish greetings", explanation=""),
            vocabulary=[],
            core_topics=["greetings"],
            search_needed=SearchNeeded(should_search=True, query_suggestions=["Swedish greetings"]),
        )

        # Mock search response with empty text (simulating failure)
        mock_search_response = ""

        mock_client = Mock()
        mock_client.search_resources.return_value = mock_search_response

        analyzer = ContentAnalyzer(settings=self.settings, client=mock_client)
        resources = analyzer.find_extra_learning_info(analysis)

        # Should return error message when LLM fails
        assert isinstance(resources, str)
        assert "No extra learning info available" in resources

    def test_fallback_analysis_structure(self):
        """Test structure of fallback analysis via parser."""
        from runestone.core.prompt_builder.parsers import ResponseParser

        parser = ResponseParser()

        # Test that fallback returns valid structure
        fallback_data = parser._fallback_analysis_parse("invalid response")

        # Check required structure
        assert isinstance(fallback_data, ContentAnalysis)
        assert isinstance(fallback_data.vocabulary, list)
        assert isinstance(fallback_data.core_topics, list)
        assert fallback_data.grammar_focus.topic == "Swedish language practice"

    def test_fallback_analysis_includes_rules_field(self):
        """Test that fallback analysis includes rules field."""
        from runestone.core.prompt_builder.parsers import ResponseParser

        parser = ResponseParser()
        fallback_data = parser._fallback_analysis_parse("invalid response")

        # Check that rules field is present and None
        assert isinstance(fallback_data, ContentAnalysis)
        assert hasattr(fallback_data.grammar_focus, "rules")
        assert fallback_data.grammar_focus.rules is None
