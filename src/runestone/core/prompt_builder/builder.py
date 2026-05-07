"""
Prompt builder for constructing LLM prompts.

This module provides the main PromptBuilder class that constructs
prompts using templates from the template registry.
"""

from typing import Dict, List, Optional

from runestone.core.constants import VOCABULARY_BATCH_SIZE
from runestone.core.prompt_builder.templates import TEMPLATE_REGISTRY, PromptTemplate
from runestone.core.prompt_builder.types import ImprovementMode, PromptType


class PromptBuilder:
    """
    Main interface for building prompts for different LLM operations.

    This class provides type-safe methods for building various prompts,
    encapsulating the template rendering logic and parameter handling.
    """

    def __init__(self, templates: Optional[Dict[PromptType, PromptTemplate]] = None):
        """
        Initialize the prompt builder.

        Args:
            templates: Optional custom template registry. If None, uses default registry.
        """
        self._templates = templates if templates is not None else TEMPLATE_REGISTRY.copy()

    def get_template(self, prompt_type: PromptType) -> PromptTemplate:
        """
        Get a template from the registry.

        Args:
            prompt_type: Type of prompt template to retrieve

        Returns:
            The requested PromptTemplate

        Raises:
            KeyError: If the prompt type is not found
        """
        return self._templates[prompt_type]

    def build_ocr_prompt(self) -> str:
        """
        Build OCR prompt for text extraction from images.

        Returns:
            Complete OCR prompt string ready for LLM

        Example:
            >>> builder = PromptBuilder()
            >>> prompt = builder.build_ocr_prompt()
        """
        template = self._templates[PromptType.OCR]
        return template.render()

    def build_analysis_prompt(self, text: str) -> str:
        """
        Build content analysis prompt for Swedish textbook pages.

        Args:
            text: Extracted text from textbook page to analyze

        Returns:
            Complete analysis prompt string

        Example:
            >>> builder = PromptBuilder()
            >>> prompt = builder.build_analysis_prompt("Swedish textbook content...")
        """
        template = self._templates[PromptType.ANALYSIS]
        return template.render(extracted_text=text)

    def build_vocabulary_prompt(self, word_phrase: str, mode: ImprovementMode = ImprovementMode.EXAMPLE_ONLY) -> str:
        """
        Build the vocabulary improvement prompt.

        All improvement modes share the same rich prompt so the model always gets
        the same linguistic context. The requested mode is applied later when the
        response is filtered for the caller.

        Args:
            word_phrase: Swedish word or phrase to improve
            mode: Type of improvement requested. The prompt is shared across
                modes; filtering happens after the model response is parsed.

        Returns:
            Complete vocabulary improvement prompt string
        """
        template = self._templates[PromptType.VOCABULARY_IMPROVE]

        params = self._build_vocabulary_params(word_phrase)

        return template.render(**params)

    def _build_vocabulary_params(self, word_phrase: str) -> Dict[str, str]:
        """
        Build parameters for the shared vocabulary template.

        Args:
            word_phrase: Swedish word or phrase

        Returns:
            Dictionary of template parameters
        """
        params = {
            "word_phrase": word_phrase,
            "content_type": "translation, example phrase and extra info",
            "translation_instruction_json": '"translation": "English translation of the word/phrase"',
            "translation_detail": ("1. For translation: Provide the most common and accurate English " "translation."),
            "example_phrase_json": (
                ',\n    "example_phrase": "A natural Swedish sentence using the ' 'word/phrase in context"'
            ),
            "example_phrase_detail": (
                "\n\n2. For example_phrase:\n    - Create a natural, conversational "
                "Swedish sentence that uses the word/phrase\n    - The sentence "
                "should clearly demonstrate the meaning and usage\n    - Keep it "
                "simple and appropriate for language learners\n    - The example "
                "should be practical and realistic\n - Provide an English translation for example."
            ),
            "extra_info_json": (
                ',\n    "extra_info": "A concise description of grammatical details '
                '(e.g., word form, base form, en/ett classification)"'
            ),
            "extra_info_detail": (
                "\n\n3. For extra_info:\n    - Provide grammatical information about "
                "the Swedish word/phrase\n    - Include word form (noun, verb, "
                "adjective, etc.), en/ett classification for nouns, base forms, verb forms (4 forms) for verbs "
                "etc.\n"
                '    - Keep it short, concise and human-readable (e.g., "en-word, noun, '
                'base form: ord")\n    - Focus on the most important grammatical '
                "details for language learners. Don't provide basic form of word if it is"
                "already in basic form. Provide comparative forms for adjectives."
            ),
        }

        return params

    def build_vocabulary_batch_prompt(self, word_phrases: List[str]) -> str:
        """
        Build batch vocabulary improvement prompt for multiple items.

        Args:
            word_phrases: List of Swedish words/phrases (max 100)

        Returns:
            Complete batch improvement prompt string

        Raises:
            ValueError: If word_phrases list is empty or exceeds 100 items
        """
        if not word_phrases:
            raise ValueError("word_phrases list cannot be empty")
        if len(word_phrases) > VOCABULARY_BATCH_SIZE:
            raise ValueError(f"Batch size {len(word_phrases)} exceeds maximum of {VOCABULARY_BATCH_SIZE}")

        template = self._templates[PromptType.VOCABULARY_BATCH_IMPROVE]

        # Format as numbered list for clarity
        word_phrases_list = "\n".join(f"{i+1}. {wp}" for i, wp in enumerate(word_phrases))

        return template.render(word_phrases_list=word_phrases_list)
