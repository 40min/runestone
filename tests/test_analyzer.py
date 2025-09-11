"""
Tests for the content analysis module.
"""

import json
from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.console import setup_console
from runestone.core.exceptions import APIKeyError, ContentAnalysisError, LLMError


class TestContentAnalyzer:
    """Test cases for ContentAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        setup_console()
        self.api_key = "test-api-key"
        self.sample_text = "Hej, jag heter Anna. Hur mår du?"
        self.settings = Settings()

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_init_success(self, mock_model, mock_configure):
        """Test successful initialization."""
        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key, verbose=True)

        mock_configure.assert_called_once_with(api_key=self.api_key)
        # GeminiClient creates two models (OCR and analysis), so expect 2 calls
        assert mock_model.call_count == 2
        assert analyzer.verbose is True

    @patch("google.generativeai.configure")
    def test_init_api_key_error(self, mock_configure):
        """Test initialization with invalid API key."""
        mock_configure.side_effect = Exception("Invalid API key")

        with pytest.raises(APIKeyError) as exc_info:
            ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)

        assert "Failed to configure Gemini API" in str(exc_info.value)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_content_success(self, mock_model_class, mock_configure):
        """Test successful content analysis."""
        # Mock analysis result
        analysis_result = {
            "grammar_focus": {
                "has_explicit_rules": True,
                "topic": "Swedish greetings",
                "explanation": "Basic greeting patterns in Swedish",
                "rules": "Hej [hello] - greeting\nHur mår du? [how are you?] - question form",
            },
            "vocabulary": [
                {"swedish": "hej", "english": "hello"},
                {"swedish": "jag heter", "english": "my name is"},
            ],
            "core_topics": ["greetings", "introductions"],
            "search_needed": {
                "should_search": True,
                "query_suggestions": ["Swedish greetings", "Swedish introductions"],
            },
        }

        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = json.dumps(analysis_result)

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)
        result = analyzer.analyze_content(self.sample_text)

        # Verify result structure
        assert isinstance(result, dict)
        assert "grammar_focus" in result
        assert "vocabulary" in result
        assert "core_topics" in result
        assert "search_needed" in result

        # Verify specific content
        assert result["grammar_focus"]["topic"] == "Swedish greetings"
        assert result["grammar_focus"]["rules"] == "Hej [hello] - greeting\nHur mår du? [how are you?] - question form"
        assert len(result["vocabulary"]) == 2
        assert result["vocabulary"][0]["swedish"] == "hej"

        # Verify rules field is present
        assert "rules" in result["grammar_focus"]

        # Verify Gemini was called correctly
        mock_model.generate_content.assert_called_once()
        args = mock_model.generate_content.call_args[0]
        assert self.sample_text in args[0]
        assert "JSON format" in args[0]

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_content_invalid_json(self, mock_model_class, mock_configure):
        """Test handling of invalid JSON response."""
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.text = "This is not valid JSON"

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)
        result = analyzer.analyze_content(self.sample_text)

        # Should get fallback analysis
        assert "fallback_used" in result
        assert result["fallback_used"] is True
        assert "grammar_focus" in result
        assert "vocabulary" in result

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_content_missing_fields(self, mock_model_class, mock_configure):
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

        mock_response = Mock()
        mock_response.text = json.dumps(incomplete_result)

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)

        with pytest.raises(ContentAnalysisError) as exc_info:
            analyzer.analyze_content(self.sample_text)

        assert "Missing required field" in str(exc_info.value)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_content_no_response(self, mock_model_class, mock_configure):
        """Test handling of empty response."""
        mock_response = Mock()
        mock_response.text = None

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)

        with pytest.raises(ContentAnalysisError) as exc_info:
            analyzer.analyze_content(self.sample_text)

        assert "No analysis returned" in str(exc_info.value)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_find_extra_learning_info_no_search_needed(self, mock_model_class, mock_configure):
        """Test resource finding when search is not needed."""
        analysis = {"search_needed": {"should_search": False, "query_suggestions": []}}

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)
        resources = analyzer.find_extra_learning_info(analysis)

        assert resources == ""

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_find_extra_learning_info_with_search(self, mock_model_class, mock_configure):
        """Test resource finding with search queries."""
        analysis = {
            "search_needed": {
                "should_search": True,
                "query_suggestions": ["Swedish greetings"],
            },
            "core_topics": ["greetings"],
            "grammar_focus": {"topic": "Swedish greetings"},
        }

        # Mock search response with educational material
        mock_search_response = Mock()
        mock_search_response.text = "Here is educational material about Swedish greetings and introductions. Swedish greetings include 'Hej' (Hi), 'God morgon' (Good morning), and 'Tack' (Thank you). Use 'Jag heter' (My name is) followed by your name."

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_search_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)
        resources = analyzer.find_extra_learning_info(analysis)

        # Should return a string with educational material
        assert isinstance(resources, str)
        assert len(resources) > 0
        assert "Swedish greetings" in resources or "introductions" in resources

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_find_extra_learning_info_fallback(self, mock_model_class, mock_configure):
        """Test fallback behavior when search fails."""
        analysis = {
            "search_needed": {
                "should_search": True,
                "query_suggestions": ["Swedish greetings"],
            },
            "core_topics": ["greetings"],
            "grammar_focus": {"topic": "Swedish greetings"},
        }

        # Mock search response with empty text (simulating failure)
        mock_search_response = Mock()
        mock_search_response.text = ""

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_search_response
        mock_model_class.return_value = mock_model

        analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)
        resources = analyzer.find_extra_learning_info(analysis)

        # Should return error message when LLM fails
        assert isinstance(resources, str)
        assert "Search failed" in resources or "Resource search failed" in resources

    def test_fallback_analysis_structure(self):
        """Test structure of fallback analysis."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)

        result = analyzer._fallback_analysis("test text", "raw response")

        # Check required structure
        assert "grammar_focus" in result
        assert "vocabulary" in result
        assert "core_topics" in result
        assert "search_needed" in result
        assert "fallback_used" in result
        assert "raw_response" in result

        assert result["fallback_used"] is True
        assert result["raw_response"] == "raw response"
        assert isinstance(result["vocabulary"], list)
        assert isinstance(result["core_topics"], list)

    def test_fallback_analysis_includes_rules_field(self):
        """Test that fallback analysis includes rules field."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            analyzer = ContentAnalyzer(settings=self.settings, provider="gemini", api_key=self.api_key)

        result = analyzer._fallback_analysis("test text", "raw response")

        # Check that rules field is present and None
        assert "grammar_focus" in result
        assert "rules" in result["grammar_focus"]
        assert result["grammar_focus"]["rules"] is None