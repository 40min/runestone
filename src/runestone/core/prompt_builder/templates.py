"""
Prompt templates and template management.

This module contains all prompt templates used throughout the application,
organized in a centralized registry for easy management and version control.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from runestone.core.prompt_builder.exceptions import ParameterMissingError
from runestone.core.prompt_builder.types import PromptType


@dataclass
class PromptTemplate:
    """Represents a prompt template with metadata and rendering capability."""

    name: str
    version: str
    content: str
    parameters: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_parameters(self, **kwargs) -> None:
        """
        Validate that all required parameters are provided.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ParameterMissingError: If required parameters are missing
        """
        missing = [param for param in self.parameters if param not in kwargs]
        if missing:
            raise ParameterMissingError(f"Missing required parameters for template '{self.name}': {', '.join(missing)}")

    def render(self, **kwargs) -> str:
        """
        Render the template with provided parameters.

        Args:
            **kwargs: Parameters to substitute in the template

        Returns:
            Rendered template string

        Raises:
            ParameterMissingError: If required parameters are missing
        """
        self.validate_parameters(**kwargs)
        return self.content.format(**kwargs)


# Template Registry - All prompt templates organized by type
TEMPLATE_REGISTRY: Dict[PromptType, PromptTemplate] = {
    PromptType.OCR: PromptTemplate(
        name="OCR Extraction",
        version="1.0.0",
        content="""
You are an expert OCR transcription assistant. Your task is to accurately transcribe all readable text
from the provided image.

## Core Instructions:
1. **Exact Transcription**: Copy text exactly as it appears, preserving:
   - Original formatting and layout
   - All punctuation marks and special characters (å, ä, ö, é, ñ, etc.)
   - Capitalization patterns
   - Number formatting and mathematical notation

2. **Content Inclusion**: Transcribe ALL visible text including:
   - Main body text and headings
   - Text within boxes, frames, or highlighted areas
   - Exercise questions and instructions
   - Notes, captions, and annotations
   - Word lists and vocabulary
   - Page numbers and headers/footers
   - Table content and labels

3. **Formatting Preservation**:
   - Maintain paragraph breaks and line spacing
   - Preserve indentation and bullet points
   - Keep table structure using simple formatting
   - Use --- or === for visual separators when present

4. **Special Handling**:
   - Underscores (_) in exercises represent blank spaces for student answers - transcribe as is
   - For unclear text, use [unclear: best_guess] or [unclear] if no guess possible
   - Mark different sections clearly if the layout suggests distinct areas

5. **Quality Control**:
   - Double-check numbers, dates, and proper names
   - Verify special characters are correctly represented
   - Ensure no text is accidentally omitted

## Output Format:
Return a JSON object with the following structure:

{{
  "transcribed_text": "The complete transcribed text from the image",
  "recognition_statistics": {{
    "total_elements": N,
    "successfully_transcribed": X,
    "unclear_uncertain": Y,
    "unable_to_recognize": Z
  }}
}}

If no readable text exists, respond with:
{{"error": "Could not recognize text on the page."}}

## Important Notes:
- Pay special attention to text in blue and light-blue boxes -- it is probably important rules or explanations
- Don't ignore text in light-blue boxes or any colored boxes (blue, dark-blue, etc.)
- Dark boxes often contain critical text content - transcribe ALL text within them exactly as it appears
- NEVER add descriptive text like "[black box with text]" or "[dark area]" - only transcribe the actual readable text
- Do NOT hallucinate or invent text that isn't clearly visible - transcribe only what you can actually read
- Be extremely precise with names, numbers, and exercise content - transcribe EXACTLY as shown, don't modify or guess
- If text is unclear or hard to read, use [unclear: best_guess] rather than changing it
- Ignore images, and non-text graphics
- Focus on text content only, not visual layout descriptions
- If text appears in multiple columns, transcribe left-to-right, top-to-bottom
- Maintain the original language of the text (don't translate)
- ACCURACY IS CRITICAL: Copy text exactly as it appears without any modifications, especially names
  and numbers in exercises
""",
        parameters=[],
        metadata={"requires_image": True, "output_format": "json"},
    ),
    PromptType.ANALYSIS: PromptTemplate(
        name="Content Analysis",
        version="1.0.0",
        content="""
You are a Swedish language learning expert. Analyze this text from a Swedish
textbook page and provide a structured learning guide.

TEXT TO ANALYZE:
```
{extracted_text}
```

Please provide your analysis in the following JSON format:

{{
    "grammar_focus": {{
        "has_explicit_rules": boolean,
        "topic": "string describing the main grammatical topic",
        "rules": "single string with rules and translations. Use newlines to separate rules, not a list",
        "explanation": "English explanation of the grammar rule or pattern"
    }},
    "vocabulary": [
        {{
            "swedish": "Swedish word or phrase",
            "english": "English translation",
            "example_phrase": "sentence from source text containing the word, or null if not available"
        }}
    ],
    "core_topics": [
        "list of main topics covered on this page"
    ],
    "search_needed": {{
        "should_search": boolean,
        "query_suggestions": ["list of search queries for finding additional resources"]
    }}
}}

INSTRUCTIONS:
1. For grammar_focus:
   - If you recognise rules listed in the text, provide them as a SINGLE STRING with translation into English
     per phrase in brackets. If multiple rules exist, separate them with newlines (\n) within the string.
     DO NOT return rules as a list or array - it must be a single string value.
   - If no rules are explicitly listed, infer them from the text and format as a single string.
   - Set has_explicit_rules to true if there's a clear grammar rule section
   - Set has_explicit_rules to false if you need to infer the grammar from exercises
   - Provide a clear English explanation of the grammatical concept

2. For vocabulary:
   - Extract all Swedish words and meaningful phrases from the text (including excercise
     description)
   - Exclude very basic function words (e.g., och, är, en, ett, han, hon, de, hen, jag, du, vi, ni, mig, dig)
     but allow basic words to appear as part of longer meaningful phrases, but not as single entries.
   - Exclude personal names
   - Lowercase all words and phrases except personal names and abbreviations.
   - Deduplicate words, but keep different forms if they appear (e.g., hund / hunden).
   - For each entry, provide the Swedish word/phrase and its most common English translation.
   - For each entry, also provide an example_phrase containing the sentence from the source text
     where the word appeared, if available. If not available, set to null.
   - List translated words in alphabetical order.

3. For core_topics:
   - Identify 2-4 main learning topics from this page
   - Use clear, descriptive terms

4. For search_needed:
    - Set should_search = true if the provided page lacks grammar explanations and only contains
      exercises, examples, or incomplete information.
    - If should_search = true, generate a list of specific and targeted search queries that would help
      find reliable grammar explanations for the identified topic(s).
    - Queries should be concise, precise, and focus on the exact grammar concept(s) missing from
      the resource.
    - If explanations are already sufficient, set should_search = false and do not generate queries.

Return ONLY valid JSON, no additional text or formatting.
""",
        parameters=["extracted_text"],
        metadata={"output_format": "json"},
    ),
    PromptType.SEARCH: PromptTemplate(
        name="Resource Search",
        version="1.0.0",
        content="""
You have web search capabilities. Search the web for educational material related to Swedish language learning.

Core topics: {core_topics}
Additional suggestions: {query_suggestions}

Instructions:
- Search the web for relevant, high-quality educational resources.
- Summarize findings into a single structured text, grouped by topic.
- For each topic, give 2–5 concise bullet points with the most useful rules, explanations, or examples.
- Explain topics as a tutor, using clear and simple language.
- Keep the text readable and compact (avoid long sections or repeated titles).
- Prioritize reliable sources such as:
  - https://swedish-for-all.se/sfi-steg-learning-steps/
  - https://sites.google.com/view/swedish-med-papegojan/
  - http://svenskgrammatik.net/Content.aspx
  - https://www.worddive.com/en/grammar/swedish-grammar/


Return only the structured educational text.

Format:
- Format the summary in plain text, not Markdown.
- Use emojis for section headers and bullets (e.g., 📌, ❓, 📖, 💡).
- Keep explanations concise and structured with short lines.
- Do not use symbols like **bold**, # headers, or markdown tables.
- Provide links to the sources you used, if applicable.
- Provide funny examples for grammar rules.
""",
        parameters=["core_topics", "query_suggestions"],
        metadata={"requires_web_search": True},
    ),
    PromptType.VOCABULARY_IMPROVE: PromptTemplate(
        name="Vocabulary Improvement",
        version="1.0.0",
        content="""
You are a Swedish language learning expert. Your task is to help improve a vocabulary entry by providing {content_type}.

SWEDISH WORD/PHRASE: {word_phrase}

Please provide your response in the following JSON format:

{{
    {translation_instruction_json}{example_phrase_json}{extra_info_json}
}}

INSTRUCTIONS:
{translation_detail}{example_phrase_detail}{extra_info_detail}

Return ONLY valid JSON, no additional text or formatting.
""",
        parameters=[
            "word_phrase",
            "content_type",
            "translation_instruction_json",
            "translation_detail",
            "example_phrase_json",
            "example_phrase_detail",
            "extra_info_json",
            "extra_info_detail",
        ],
        metadata={"output_format": "json"},
    ),
}


def get_template(prompt_type: PromptType) -> PromptTemplate:
    """
    Get a template from the registry by type.

    Args:
        prompt_type: The type of prompt template to retrieve

    Returns:
        The requested PromptTemplate

    Raises:
        KeyError: If the prompt type is not found in the registry
    """
    return TEMPLATE_REGISTRY[prompt_type]


def get_all_templates() -> Dict[PromptType, PromptTemplate]:
    """
    Get all templates from the registry.

    Returns:
        Dictionary mapping prompt types to templates
    """
    return TEMPLATE_REGISTRY.copy()
