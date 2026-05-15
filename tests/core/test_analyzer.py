"""Tests for the content analysis module."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.exceptions import OutputParserException

from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.console import setup_console
from runestone.core.exceptions import ContentAnalysisError
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, VocabularyItem


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
        mock_model = Mock()
        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model, verbose=True)

        assert analyzer.model == mock_model
        assert analyzer.verbose is True

    @pytest.mark.anyio
    async def test_analyze_content_success(self):
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
        )

        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.return_value = analysis_result
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)
        result = await analyzer.analyze_content(self.sample_text)

        # Verify result structure
        assert isinstance(result, ContentAnalysis)
        assert isinstance(result.grammar_focus, GrammarFocus)
        assert isinstance(result.vocabulary, list)
        assert isinstance(result.core_topics, list)

        # Verify specific content
        assert result.grammar_focus.topic == "Swedish greetings"
        assert result.grammar_focus.rules == "Hej [hello] - greeting\nHur mår du? [how are you?] - question form"
        assert len(result.vocabulary) == 2
        assert result.vocabulary[0].swedish == "hej"

        # Verify rules field is present
        assert hasattr(result.grammar_focus, "rules")

        # Verify client was called correctly
        mock_model.with_structured_output.assert_called_once_with(ContentAnalysis)
        structured_model.ainvoke.assert_called_once()
        args = structured_model.ainvoke.call_args[0]
        assert self.sample_text in args[0]
        assert "JSON format" in args[0]

    @pytest.mark.anyio
    async def test_analyze_content_accepts_dict_payload(self):
        """Accept a plain mapping when the structured model does not return the schema instance."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.return_value = {
            "grammar_focus": {
                "has_explicit_rules": True,
                "topic": "Swedish greetings",
                "rules": "Hej [hello] - greeting",
                "explanation": "Basic greeting patterns in Swedish",
            },
            "vocabulary": [
                {"swedish": "hej", "english": "hello", "example_phrase": None, "known": False},
            ],
            "core_topics": ["greetings"],
        }
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)
        result = await analyzer.analyze_content(self.sample_text)

        assert isinstance(result, ContentAnalysis)
        assert result.grammar_focus.topic == "Swedish greetings"
        assert result.vocabulary[0].swedish == "hej"

    @pytest.mark.anyio
    async def test_analyze_content_uses_default_structured_output_method(self):
        """Use the provider-default structured output method for content analysis."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.return_value = ContentAnalysis(
            grammar_focus=GrammarFocus(
                has_explicit_rules=False,
                topic="Greetings",
                explanation="Greeting practice",
                rules=None,
            ),
            vocabulary=[],
            core_topics=["greetings"],
        )
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)
        await analyzer.analyze_content(self.sample_text)

        mock_model.with_structured_output.assert_called_once_with(ContentAnalysis)

    @pytest.mark.anyio
    async def test_analyze_content_validation_failure(self):
        """Raise a content-analysis error when structured parsing fails."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.side_effect = OutputParserException("bad schema output")
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)

        with pytest.raises(ContentAnalysisError, match="Structured content analysis validation failed"):
            await analyzer.analyze_content(self.sample_text)

    @pytest.mark.anyio
    async def test_analyze_content_none_response(self):
        """Raise a content-analysis error when the structured model returns no data."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.return_value = None
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)

        with pytest.raises(ContentAnalysisError, match="No analysis returned from LLM"):
            await analyzer.analyze_content(self.sample_text)

    @pytest.mark.anyio
    async def test_analyze_content_model_validate_failure(self):
        """Wrap schema validation failures from plain mappings."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.return_value = {
            "grammar_focus": {
                "has_explicit_rules": True,
                "topic": "Swedish greetings",
            }
        }
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)

        with pytest.raises(ContentAnalysisError, match="Content analysis failed"):
            await analyzer.analyze_content(self.sample_text)

    @pytest.mark.anyio
    async def test_analyze_content_runtime_failure(self):
        """Wrap unexpected structured-output failures as content-analysis errors."""
        mock_model = Mock()
        structured_model = AsyncMock()
        structured_model.ainvoke.side_effect = RuntimeError("provider unavailable")
        mock_model.with_structured_output.return_value = structured_model

        analyzer = ContentAnalyzer(settings=self.settings, model=mock_model)

        with pytest.raises(ContentAnalysisError) as exc_info:
            await analyzer.analyze_content(self.sample_text)

        assert "Content analysis failed: provider unavailable" in str(exc_info.value)

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
