"""
Tests for prompt templates.
"""

import pytest

from runestone.core.prompt_builder.exceptions import ParameterMissingError
from runestone.core.prompt_builder.templates import TEMPLATE_REGISTRY, PromptTemplate, get_all_templates, get_template
from runestone.core.prompt_builder.types import PromptType


class TestPromptTemplate:
    """Test cases for PromptTemplate class."""

    def test_create_template_with_no_parameters(self):
        """Test creating a template with no required parameters."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="This is a test template without parameters.",
            parameters=[],
        )

        assert template.name == "Test Template"
        assert template.version == "1.0.0"
        assert template.content == "This is a test template without parameters."
        assert template.parameters == []

    def test_create_template_with_parameters(self):
        """Test creating a template with required parameters."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Hello {name}, you are {age} years old.",
            parameters=["name", "age"],
        )

        assert template.parameters == ["name", "age"]

    def test_render_template_with_all_parameters(self):
        """Test rendering a template with all required parameters provided."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Hello {name}, you are {age} years old.",
            parameters=["name", "age"],
        )

        result = template.render(name="Alice", age=30)
        assert result == "Hello Alice, you are 30 years old."

    def test_render_template_without_parameters(self):
        """Test rendering a template with no parameters."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="This is a static template.",
            parameters=[],
        )

        result = template.render()
        assert result == "This is a static template."

    def test_render_template_missing_parameter_raises_error(self):
        """Test that rendering fails when required parameters are missing."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Hello {name}, you are {age} years old.",
            parameters=["name", "age"],
        )

        with pytest.raises(ParameterMissingError) as exc_info:
            template.render(name="Alice")

        assert "Missing required parameters" in str(exc_info.value)
        assert "age" in str(exc_info.value)

    def test_render_template_with_extra_parameters(self):
        """Test rendering with extra parameters (should not cause error)."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Hello {name}.",
            parameters=["name"],
        )

        result = template.render(name="Alice", age=30, city="Stockholm")
        assert result == "Hello Alice."

    def test_validate_parameters_success(self):
        """Test parameter validation succeeds with all required parameters."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Hello {name}.",
            parameters=["name"],
        )

        # Should not raise any exception
        template.validate_parameters(name="Alice")

    def test_validate_parameters_multiple_missing(self):
        """Test parameter validation with multiple missing parameters."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Test {param1} and {param2} and {param3}.",
            parameters=["param1", "param2", "param3"],
        )

        with pytest.raises(ParameterMissingError) as exc_info:
            template.validate_parameters(param1="value1")

        error_message = str(exc_info.value)
        assert "param2" in error_message
        assert "param3" in error_message

    def test_template_with_metadata(self):
        """Test creating a template with metadata."""
        template = PromptTemplate(
            name="Test Template",
            version="1.0.0",
            content="Test content.",
            parameters=[],
            metadata={"output_format": "json", "requires_image": True},
        )

        assert template.metadata["output_format"] == "json"
        assert template.metadata["requires_image"] is True


class TestTemplateRegistry:
    """Test cases for template registry."""

    def test_registry_contains_all_prompt_types(self):
        """Test that registry contains templates for all prompt types."""
        for prompt_type in PromptType:
            assert prompt_type in TEMPLATE_REGISTRY
            assert isinstance(TEMPLATE_REGISTRY[prompt_type], PromptTemplate)

    def test_ocr_template_exists(self):
        """Test OCR template exists and has correct structure."""
        ocr_template = TEMPLATE_REGISTRY[PromptType.OCR]
        assert ocr_template.name == "OCR Extraction"
        assert ocr_template.version == "1.0.0"
        assert ocr_template.parameters == []
        assert "transcribe" in ocr_template.content.lower()
        assert ocr_template.metadata.get("requires_image") is True

    def test_analysis_template_exists(self):
        """Test analysis template exists and has correct structure."""
        analysis_template = TEMPLATE_REGISTRY[PromptType.ANALYSIS]
        assert analysis_template.name == "Content Analysis"
        assert analysis_template.version == "1.0.0"
        assert "extracted_text" in analysis_template.parameters
        assert "vocabulary" in analysis_template.content.lower()

    def test_vocabulary_improve_template_exists(self):
        """Test vocabulary improvement template exists and has correct structure."""
        vocab_template = TEMPLATE_REGISTRY[PromptType.VOCABULARY_IMPROVE]
        assert vocab_template.name == "Vocabulary Improvement"
        assert "word_phrase" in vocab_template.parameters
        assert "content_type" in vocab_template.parameters
        assert len(vocab_template.parameters) > 2  # Has multiple parameters

    def test_get_template_function(self):
        """Test get_template utility function."""
        ocr_template = get_template(PromptType.OCR)
        assert isinstance(ocr_template, PromptTemplate)
        assert ocr_template.name == "OCR Extraction"

    def test_get_template_raises_keyerror_for_invalid_type(self):
        """Test get_template raises KeyError for invalid type."""
        with pytest.raises(KeyError):
            get_template("invalid_type")

    def test_get_all_templates_returns_copy(self):
        """Test get_all_templates returns a copy of the registry."""
        templates = get_all_templates()
        assert len(templates) == len(TEMPLATE_REGISTRY)

        # Verify it's a copy by modifying it
        original_count = len(TEMPLATE_REGISTRY)
        templates.clear()
        assert len(TEMPLATE_REGISTRY) == original_count

    def test_vocabulary_template_parameters_complete(self):
        """Test vocabulary template has all required parameters."""
        vocab_template = TEMPLATE_REGISTRY[PromptType.VOCABULARY_IMPROVE]

        required_params = [
            "word_phrase",
            "content_type",
            "translation_instruction_json",
            "translation_detail",
            "example_phrase_json",
            "example_phrase_detail",
            "extra_info_json",
            "extra_info_detail",
        ]

        for param in required_params:
            assert param in vocab_template.parameters, f"Missing parameter: {param}"


class TestTemplateContent:
    """Test cases for template content quality."""

    def test_ocr_template_has_json_output_instruction(self):
        """Test OCR template instructs JSON output."""
        ocr_template = TEMPLATE_REGISTRY[PromptType.OCR]
        assert "json" in ocr_template.content.lower()
        assert "transcribed_text" in ocr_template.content

    def test_analysis_template_has_structured_output(self):
        """Test analysis template requests structured output."""
        analysis_template = TEMPLATE_REGISTRY[PromptType.ANALYSIS]
        content = analysis_template.content
        assert "grammar_focus" in content
        assert "vocabulary" in content
        assert "core_topics" in content

    def test_vocabulary_template_supports_modes(self):
        """Test vocabulary template supports different improvement modes."""
        vocab_template = TEMPLATE_REGISTRY[PromptType.VOCABULARY_IMPROVE]
        content = vocab_template.content

        # Should have placeholders for all mode-specific content
        assert "{translation_instruction_json}" in content
        assert "{example_phrase_json}" in content
        assert "{extra_info_json}" in content
        assert "{content_type}" in content
