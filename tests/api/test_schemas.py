"""
Tests for API schemas and data models.

This module tests the Pydantic models defined in schemas.py,
including validation, serialization, and error handling.
"""

import pytest
from pydantic import ValidationError

from runestone.api.schemas import (
    AnalysisRequest,
    CheatsheetContent,
    CheatsheetInfo,
    ContentAnalysis,
    ErrorResponse,
    GrammarFocus,
    HealthResponse,
    ResourceRequest,
    ResourceRequestData,
    ResourceResponse,
    SearchNeeded,
    Vocabulary,
    VocabularyItem,
    VocabularyItemCreate,
    VocabularySaveRequest,
)
from runestone.schemas.ocr import OCRResult, RecognitionStatistics


class TestOCRResult:
    """Test cases for OCRResult schema."""

    def test_valid_ocr_result(self):
        """Test creating a valid OCRResult."""
        stats = RecognitionStatistics(
            total_elements=10, successfully_transcribed=10, unclear_uncertain=0, unable_to_recognize=0
        )
        result = OCRResult(transcribed_text="Hello world", recognition_statistics=stats)
        assert result.transcribed_text == "Hello world"
        assert result.character_count == 11

    def test_ocr_result_serialization(self):
        """Test OCRResult serialization to dict."""
        stats = RecognitionStatistics(
            total_elements=5, successfully_transcribed=5, unclear_uncertain=0, unable_to_recognize=0
        )
        result = OCRResult(transcribed_text="Test", recognition_statistics=stats)
        # Use by_alias=True to get the API format with aliases
        data = result.model_dump(by_alias=True)
        # Check that serialization uses aliases: transcribed_text -> text
        assert data["text"] == "Test"
        assert data["character_count"] == 4
        assert "recognition_statistics" in data


class TestGrammarFocus:
    """Test cases for GrammarFocus schema."""

    def test_valid_grammar_focus(self):
        """Test creating a valid GrammarFocus."""
        focus = GrammarFocus(
            topic="Swedish questions",
            explanation="Basic question formation",
            has_explicit_rules=True,
            rules="Use 'vad' for what questions",
        )
        assert focus.topic == "Swedish questions"
        assert focus.has_explicit_rules is True
        assert focus.rules == "Use 'vad' for what questions"

    def test_grammar_focus_optional_rules(self):
        """Test GrammarFocus with optional rules."""
        focus = GrammarFocus(topic="Greetings", explanation="Common greetings", has_explicit_rules=False)
        assert focus.rules is None


class TestVocabularyItem:
    """Test cases for VocabularyItem schema."""

    def test_valid_vocabulary_item(self):
        """Test creating a valid VocabularyItem."""
        item = VocabularyItem(swedish="hej", english="hello", example_phrase="Hej, hur mår du?")
        assert item.swedish == "hej"
        assert item.english == "hello"
        assert item.example_phrase == "Hej, hur mår du?"

    def test_vocabulary_item_optional_example(self):
        """Test VocabularyItem without example phrase."""
        item = VocabularyItem(swedish="tack", english="thank you")
        assert item.example_phrase is None


class TestSearchNeeded:
    """Test cases for SearchNeeded schema."""

    def test_valid_search_needed(self):
        """Test creating a valid SearchNeeded."""
        search = SearchNeeded(should_search=True, query_suggestions=["Swedish grammar", "Question formation"])
        assert search.should_search is True
        assert len(search.query_suggestions) == 2


class TestContentAnalysis:
    """Test cases for ContentAnalysis schema."""

    def test_valid_content_analysis(self):
        """Test creating a valid ContentAnalysis."""
        analysis = ContentAnalysis(
            grammar_focus=GrammarFocus(topic="Questions", explanation="Question formation", has_explicit_rules=False),
            vocabulary=[
                VocabularyItem(swedish="vad", english="what"),
                VocabularyItem(swedish="heter", english="called"),
            ],
            core_topics=["questions", "introductions"],
            search_needed=SearchNeeded(should_search=True, query_suggestions=["Swedish questions"]),
        )
        assert analysis.grammar_focus.topic == "Questions"
        assert len(analysis.vocabulary) == 2
        assert analysis.core_topics == ["questions", "introductions"]


class TestAnalysisRequest:
    """Test cases for AnalysisRequest schema."""

    def test_valid_analysis_request(self):
        """Test creating a valid AnalysisRequest."""
        request = AnalysisRequest(text="Hej, vad heter du?")
        assert request.text == "Hej, vad heter du?"

    def test_empty_text_validation(self):
        """Test AnalysisRequest with empty text."""
        # Should allow empty string as it's valid input
        request = AnalysisRequest(text="")
        assert request.text == ""


class TestResourceRequest:
    """Test cases for ResourceRequest schema."""

    def test_valid_resource_request(self):
        """Test creating a valid ResourceRequest."""
        request_data = ResourceRequestData(
            core_topics=["questions"],
            search_needed=SearchNeeded(should_search=True, query_suggestions=["Swedish questions"]),
        )
        request = ResourceRequest(analysis=request_data)
        assert request.analysis.core_topics == ["questions"]


class TestResourceResponse:
    """Test cases for ResourceResponse schema."""

    def test_valid_resource_response(self):
        """Test creating a valid ResourceResponse."""
        response = ResourceResponse(extra_info="Additional learning resources")
        assert response.extra_info == "Additional learning resources"


class TestErrorResponse:
    """Test cases for ErrorResponse schema."""

    def test_valid_error_response(self):
        """Test creating a valid ErrorResponse."""
        error = ErrorResponse(error="Processing failed", details="OCR error")
        assert error.error == "Processing failed"
        assert error.details == "OCR error"

    def test_error_response_optional_details(self):
        """Test ErrorResponse without details."""
        error = ErrorResponse(error="Validation error")
        assert error.details is None


class TestHealthResponse:
    """Test cases for HealthResponse schema."""

    def test_valid_health_response(self):
        """Test creating a valid HealthResponse."""
        health = HealthResponse(status="healthy", version="1.0.0")
        assert health.status == "healthy"
        assert health.version == "1.0.0"

    def test_health_response_default_version(self):
        """Test HealthResponse with default version."""
        health = HealthResponse(status="unhealthy")
        assert health.version == "1.0.0"


class TestVocabularySchemas:
    """Test cases for vocabulary-related schemas."""

    def test_vocabulary_item_create(self):
        """Test VocabularyItemCreate schema."""
        item = VocabularyItemCreate(
            word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple"
        )
        assert item.word_phrase == "ett äpple"
        assert item.translation == "an apple"

    def test_vocabulary_save_request(self):
        """Test VocabularySaveRequest schema."""
        request = VocabularySaveRequest(
            items=[
                VocabularyItemCreate(word_phrase="hej", translation="hello"),
                VocabularyItemCreate(word_phrase="tack", translation="thank you"),
            ]
        )
        assert len(request.items) == 2

    def test_vocabulary_response(self):
        """Test Vocabulary response schema."""
        vocab = Vocabulary(
            id=1,
            user_id=1,
            word_phrase="hej",
            translation="hello",
            example_phrase="Hej, hur mår du?",
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
        )
        assert vocab.id == 1
        assert vocab.word_phrase == "hej"


class TestSchemaValidation:
    """Test cases for schema validation errors."""

    def test_invalid_ocr_result(self):
        """Test OCRResult with invalid data."""
        with pytest.raises(ValidationError):
            # recognition_statistics should be RecognitionStatistics object, not string
            OCRResult(transcribed_text="Hello", recognition_statistics="invalid")

    def test_missing_required_fields(self):
        """Test schema with missing required fields."""
        with pytest.raises(ValidationError):
            OCRResult()  # Missing required fields (transcribed_text and recognition_statistics)

    def test_invalid_search_needed(self):
        """Test SearchNeeded with invalid query_suggestions type."""
        with pytest.raises(ValidationError):
            SearchNeeded(should_search=True, query_suggestions="invalid")  # Should be list


class TestCheatsheetSchemas:
    """Test cases for cheatsheet-related schemas."""

    def test_cheatsheet_info_with_category(self):
        """Test CheatsheetInfo schema with category field."""
        info = CheatsheetInfo(filename="adjectiv-komparation.md", title="Adjectiv Komparation", category="adjectives")
        assert info.filename == "adjectiv-komparation.md"
        assert info.title == "Adjectiv Komparation"
        assert info.category == "adjectives"

    def test_cheatsheet_info_general_category(self):
        """Test CheatsheetInfo schema with General category."""
        info = CheatsheetInfo(filename="pronunciation.md", title="Pronunciation", category="General")
        assert info.filename == "pronunciation.md"
        assert info.title == "Pronunciation"
        assert info.category == "General"

    def test_cheatsheet_info_nested_path(self):
        """Test CheatsheetInfo schema with nested file path."""
        info = CheatsheetInfo(filename="verbs/hjalpverb.md", title="Hjalpverb", category="verbs")
        assert info.filename == "verbs/hjalpverb.md"
        assert info.title == "Hjalpverb"
        assert info.category == "verbs"

    def test_cheatsheet_info_serialization(self):
        """Test CheatsheetInfo serialization to dict."""
        info = CheatsheetInfo(filename="test.md", title="Test", category="General")
        data = info.model_dump()
        assert data == {"filename": "test.md", "title": "Test", "category": "General"}

    def test_cheatsheet_content(self):
        """Test CheatsheetContent schema."""
        content = CheatsheetContent(content="# Test Content\n\nThis is test content.")
        assert content.content == "# Test Content\n\nThis is test content."

    def test_cheatsheet_content_empty(self):
        """Test CheatsheetContent schema with empty content."""
        content = CheatsheetContent(content="")
        assert content.content == ""

    def test_cheatsheet_info_missing_required_fields(self):
        """Test CheatsheetInfo with missing required fields."""
        with pytest.raises(ValidationError):
            CheatsheetInfo(filename="test.md", title="Test")  # Missing category

        with pytest.raises(ValidationError):
            CheatsheetInfo(filename="test.md", category="General")  # Missing title

        with pytest.raises(ValidationError):
            CheatsheetInfo(title="Test", category="General")  # Missing filename
