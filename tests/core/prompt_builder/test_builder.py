"""
Tests for prompt builder.
"""

import pytest

from runestone.core.prompt_builder.builder import PromptBuilder
from runestone.core.prompt_builder.templates import TEMPLATE_REGISTRY, PromptTemplate
from runestone.core.prompt_builder.types import ImprovementMode, PromptType


class TestPromptBuilderInit:
    """Test cases for PromptBuilder initialization."""

    def test_init_with_default_templates(self):
        """Test initializing builder with default templates."""
        builder = PromptBuilder()
        assert builder._templates is not None
        assert len(builder._templates) == len(TEMPLATE_REGISTRY)

    def test_init_with_custom_templates(self):
        """Test initializing builder with custom templates."""
        custom_template = PromptTemplate(
            name="Custom",
            version="1.0.0",
            content="Custom content",
            parameters=[],
        )
        custom_templates = {PromptType.OCR: custom_template}

        builder = PromptBuilder(templates=custom_templates)
        assert builder._templates[PromptType.OCR] == custom_template

    def test_init_does_not_modify_original_registry(self):
        """Test that initializing builder doesn't modify the original registry."""
        original_count = len(TEMPLATE_REGISTRY)
        builder = PromptBuilder()

        # Modify builder's templates
        builder._templates.clear()

        # Original registry should remain unchanged
        assert len(TEMPLATE_REGISTRY) == original_count


class TestPromptBuilderGetTemplate:
    """Test cases for getting templates."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_get_template_ocr(self):
        """Test getting OCR template."""
        template = self.builder.get_template(PromptType.OCR)
        assert isinstance(template, PromptTemplate)
        assert template.name == "OCR Extraction"

    def test_get_template_analysis(self):
        """Test getting analysis template."""
        template = self.builder.get_template(PromptType.ANALYSIS)
        assert isinstance(template, PromptTemplate)
        assert template.name == "Content Analysis"

    def test_get_template_raises_keyerror_for_invalid_type(self):
        """Test get_template raises KeyError for invalid type."""
        with pytest.raises(KeyError):
            self.builder.get_template("invalid")


class TestBuildOCRPrompt:
    """Test cases for building OCR prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_ocr_prompt_returns_string(self):
        """Test build_ocr_prompt returns a string."""
        prompt = self.builder.build_ocr_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_ocr_prompt_contains_expected_content(self):
        """Test OCR prompt contains expected instructions."""
        prompt = self.builder.build_ocr_prompt()
        assert "transcribe" in prompt.lower() or "ocr" in prompt.lower()
        assert "json" in prompt.lower()

    def test_build_ocr_prompt_no_parameters_needed(self):
        """Test OCR prompt can be built without parameters."""
        # Should not raise any exception
        prompt = self.builder.build_ocr_prompt()
        assert prompt is not None


class TestBuildAnalysisPrompt:
    """Test cases for building analysis prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_analysis_prompt_with_text(self):
        """Test building analysis prompt with text."""
        text = "Hej! Hur mår du? Detta är svensk text."
        prompt = self.builder.build_analysis_prompt(text)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert text in prompt

    def test_build_analysis_prompt_contains_expected_structure(self):
        """Test analysis prompt requests structured output."""
        prompt = self.builder.build_analysis_prompt("Test text")

        assert "grammar_focus" in prompt
        assert "vocabulary" in prompt
        assert "core_topics" in prompt

    def test_build_analysis_prompt_with_empty_text(self):
        """Test building analysis prompt with empty text."""
        prompt = self.builder.build_analysis_prompt("")
        assert isinstance(prompt, str)
        # Empty text should still be in the prompt (as an empty section)
        assert prompt is not None


class TestBuildSearchPrompt:
    """Test cases for building search prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_search_prompt_with_topics_and_queries(self):
        """Test building search prompt with topics and queries."""
        core_topics = ["Swedish verbs", "Present tense", "Conjugation"]
        query_suggestions = [
            "Swedish present tense conjugation",
            "Swedish verb endings",
        ]

        prompt = self.builder.build_search_prompt(core_topics, query_suggestions)

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_search_prompt_formats_topics_with_quotes(self):
        """Test search prompt formats topics with quotes."""
        core_topics = ["Topic 1", "Topic 2"]
        query_suggestions = ["Query 1"]

        prompt = self.builder.build_search_prompt(core_topics, query_suggestions)

        # Topics should be quoted in the prompt
        assert '"Topic 1"' in prompt
        assert '"Topic 2"' in prompt

    def test_build_search_prompt_formats_queries_with_quotes(self):
        """Test search prompt formats queries with quotes."""
        core_topics = ["Topic"]
        query_suggestions = ["Query 1", "Query 2"]

        prompt = self.builder.build_search_prompt(core_topics, query_suggestions)

        # Queries should be quoted in the prompt
        assert '"Query 1"' in prompt
        assert '"Query 2"' in prompt

    def test_build_search_prompt_limits_topics_to_three(self):
        """Test search prompt limits topics to first 3."""
        core_topics = ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]
        query_suggestions = ["Query"]

        prompt = self.builder.build_search_prompt(core_topics, query_suggestions)

        # First 3 should be present
        assert '"Topic 1"' in prompt
        assert '"Topic 2"' in prompt
        assert '"Topic 3"' in prompt
        # 4th and 5th should not be present
        assert '"Topic 4"' not in prompt
        assert '"Topic 5"' not in prompt

    def test_build_search_prompt_limits_queries_to_four(self):
        """Test search prompt limits queries to first 4."""
        core_topics = ["Topic"]
        query_suggestions = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]

        prompt = self.builder.build_search_prompt(core_topics, query_suggestions)

        # First 4 should be present
        assert '"Q1"' in prompt
        assert '"Q2"' in prompt
        assert '"Q3"' in prompt
        assert '"Q4"' in prompt
        # 5th and 6th should not be present
        assert '"Q5"' not in prompt
        assert '"Q6"' not in prompt

    def test_build_search_prompt_with_empty_lists(self):
        """Test building search prompt with empty lists."""
        prompt = self.builder.build_search_prompt([], [])
        assert isinstance(prompt, str)


class TestBuildVocabularyPrompt:
    """Test cases for building vocabulary improvement prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_vocabulary_prompt_example_only_mode(self):
        """Test building vocabulary prompt in EXAMPLE_ONLY mode."""
        word_phrase = "hund"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.EXAMPLE_ONLY)

        assert isinstance(prompt, str)
        assert word_phrase in prompt
        assert "example phrase" in prompt.lower()
        # Should not request translation or extra info
        assert "translation" not in prompt.lower() or '"translation"' not in prompt

    def test_build_vocabulary_prompt_extra_info_only_mode(self):
        """Test building vocabulary prompt in EXTRA_INFO_ONLY mode."""
        word_phrase = "katt"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.EXTRA_INFO_ONLY)

        assert isinstance(prompt, str)
        assert word_phrase in prompt
        assert "extra info" in prompt.lower() or "extra_info" in prompt
        # Should not request translation or example
        assert "translation" not in prompt.lower() or '"translation"' not in prompt

    def test_build_vocabulary_prompt_all_fields_mode(self):
        """Test building vocabulary prompt in ALL_FIELDS mode."""
        word_phrase = "bil"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.ALL_FIELDS)

        assert isinstance(prompt, str)
        assert word_phrase in prompt
        # Should request all fields
        assert "translation" in prompt.lower()
        assert "example" in prompt.lower()
        assert "extra" in prompt.lower()

    def test_build_vocabulary_prompt_default_mode(self):
        """Test building vocabulary prompt with default mode (EXAMPLE_ONLY)."""
        word_phrase = "hus"
        prompt = self.builder.build_vocabulary_prompt(word_phrase)

        assert isinstance(prompt, str)
        assert word_phrase in prompt
        # Default should be EXAMPLE_ONLY
        assert "example" in prompt.lower()

    def test_build_vocabulary_prompt_with_special_characters(self):
        """Test building vocabulary prompt with Swedish special characters."""
        word_phrase = "älska"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.ALL_FIELDS)

        assert word_phrase in prompt

    def test_build_vocabulary_prompt_with_phrase(self):
        """Test building vocabulary prompt with a phrase."""
        word_phrase = "tycka om"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.ALL_FIELDS)

        assert word_phrase in prompt


class TestBuildVocabularyParams:
    """Test cases for _build_vocabulary_params method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_params_all_fields_mode(self):
        """Test building parameters for ALL_FIELDS mode."""
        params = self.builder._build_vocabulary_params("test", ImprovementMode.ALL_FIELDS)

        assert params["word_phrase"] == "test"
        assert "translation, example phrase and extra info" in params["content_type"]
        assert params["translation_instruction_json"] != ""
        assert params["translation_detail"] != ""
        assert params["example_phrase_json"] != ""
        assert params["example_phrase_detail"] != ""
        assert params["extra_info_json"] != ""
        assert params["extra_info_detail"] != ""

    def test_build_params_example_only_mode(self):
        """Test building parameters for EXAMPLE_ONLY mode."""
        params = self.builder._build_vocabulary_params("test", ImprovementMode.EXAMPLE_ONLY)

        assert params["word_phrase"] == "test"
        assert "example phrase" in params["content_type"]
        # Translation and extra_info should be empty
        assert params["translation_instruction_json"] == ""
        assert params["translation_detail"] == ""
        assert params["extra_info_json"] == ""
        assert params["extra_info_detail"] == ""
        # Example phrase should be populated
        assert params["example_phrase_json"] != ""
        assert params["example_phrase_detail"] != ""
        # Example phrase should not have leading comma
        assert not params["example_phrase_json"].startswith(",")

    def test_build_params_extra_info_only_mode(self):
        """Test building parameters for EXTRA_INFO_ONLY mode."""
        params = self.builder._build_vocabulary_params("test", ImprovementMode.EXTRA_INFO_ONLY)

        assert params["word_phrase"] == "test"
        assert "extra info" in params["content_type"]
        # Translation and example should be empty
        assert params["translation_instruction_json"] == ""
        assert params["translation_detail"] == ""
        assert params["example_phrase_json"] == ""
        assert params["example_phrase_detail"] == ""
        # Extra info should be populated
        assert params["extra_info_json"] != ""
        assert params["extra_info_detail"] != ""
        # Extra info should not have leading comma
        assert not params["extra_info_json"].startswith(",")

    def test_build_params_all_modes_have_word_phrase(self):
        """Test all modes include word_phrase parameter."""
        for mode in ImprovementMode:
            params = self.builder._build_vocabulary_params("testord", mode)
            assert params["word_phrase"] == "testord"

    def test_build_params_all_modes_have_content_type(self):
        """Test all modes include content_type parameter."""
        for mode in ImprovementMode:
            params = self.builder._build_vocabulary_params("test", mode)
            assert params["content_type"] != ""
            assert isinstance(params["content_type"], str)

    def test_build_params_numbering_consistency(self):
        """Test that instruction numbering is consistent for each mode."""
        # EXAMPLE_ONLY should have "1. For example_phrase"
        params_example = self.builder._build_vocabulary_params("test", ImprovementMode.EXAMPLE_ONLY)
        assert "1. For example_phrase" in params_example["example_phrase_detail"]

        # EXTRA_INFO_ONLY should have "1. For extra_info"
        params_extra = self.builder._build_vocabulary_params("test", ImprovementMode.EXTRA_INFO_ONLY)
        assert "1. For extra_info" in params_extra["extra_info_detail"]

        # ALL_FIELDS should have numbered instructions
        params_all = self.builder._build_vocabulary_params("test", ImprovementMode.ALL_FIELDS)
        assert "1. For translation" in params_all["translation_detail"]
        assert "2. For example_phrase" in params_all["example_phrase_detail"]
        assert "3. For extra_info" in params_all["extra_info_detail"]
