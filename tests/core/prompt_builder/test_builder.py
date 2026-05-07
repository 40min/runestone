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


class TestBuildVocabularyPrompt:
    """Test cases for building vocabulary improvement prompts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = PromptBuilder()

    def test_build_vocabulary_prompt_contains_shared_rich_instructions(self):
        """Test the shared vocabulary prompt contains all rich fields and instructions."""
        word_phrase = "hund"
        prompt = self.builder.build_vocabulary_prompt(word_phrase, ImprovementMode.ALL_FIELDS)

        assert isinstance(prompt, str)
        assert word_phrase in prompt
        assert '"translation"' in prompt
        assert '"example_phrase"' in prompt
        assert '"extra_info"' in prompt
        assert "1. For translation" in prompt
        assert "2. For example_phrase" in prompt
        assert "3. For extra_info" in prompt

    def test_build_vocabulary_prompt_is_shared_across_modes(self):
        """Test all improvement modes reuse the same prompt structure."""
        word_phrase = "hus"
        prompts = {mode: self.builder.build_vocabulary_prompt(word_phrase, mode) for mode in ImprovementMode}

        assert prompts[ImprovementMode.EXAMPLE_ONLY] == prompts[ImprovementMode.EXTRA_INFO_ONLY]
        assert prompts[ImprovementMode.EXTRA_INFO_ONLY] == prompts[ImprovementMode.ALL_FIELDS]

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

    def test_build_params_returns_shared_rich_structure(self):
        """Test vocabulary params always contain the full shared prompt structure."""
        params = self.builder._build_vocabulary_params("test")

        assert params["word_phrase"] == "test"
        assert "translation, example phrase and extra info" in params["content_type"]
        assert params["translation_instruction_json"] != ""
        assert params["translation_detail"] != ""
        assert params["example_phrase_json"] != ""
        assert params["example_phrase_detail"] != ""
        assert params["extra_info_json"] != ""
        assert params["extra_info_detail"] != ""

    def test_build_params_all_modes_have_word_phrase(self):
        """Test all modes include word_phrase parameter."""
        for mode in ImprovementMode:
            params = self.builder._build_vocabulary_params("testord")
            assert params["word_phrase"] == "testord"

    def test_build_params_all_modes_have_content_type(self):
        """Test all modes include content_type parameter."""
        for mode in ImprovementMode:
            params = self.builder._build_vocabulary_params("test")
            assert params["content_type"] != ""
            assert isinstance(params["content_type"], str)

    def test_build_params_are_identical_across_modes(self):
        """Test all improvement modes reuse the same prompt parameters."""
        params_by_mode = {mode: self.builder._build_vocabulary_params("test") for mode in ImprovementMode}

        assert params_by_mode[ImprovementMode.EXAMPLE_ONLY] == params_by_mode[ImprovementMode.EXTRA_INFO_ONLY]
        assert params_by_mode[ImprovementMode.EXTRA_INFO_ONLY] == params_by_mode[ImprovementMode.ALL_FIELDS]
