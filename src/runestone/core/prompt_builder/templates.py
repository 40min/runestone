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

## Stage 1 — Layout Description (do not transcribe yet)
1. briefly analyze and describe the page layout before transcription.
Identify:
- The number of distinct text areas (e.g., 1 column, 2 columns, or side-by-side exercises)
- Each labeled section or heading (e.g., A, B, FOKUS, etc.)
- The approximate reading order (top-to-bottom, left-to-right)
- Whether any sections appear horizontally aligned (side by side)
2. **Return the layout summary only** as plain text
3. **Then immediately continue to Stage 2** — do **not stop after Stage 1**


Make sure the Stage 1 output ends with this exact line (to trigger continuation):

> [END OF STAGE 1 — CONTINUE TO STAGE 2]

---

## Stage 2 — Text Transcription
Now transcribe all visible text **exactly as it appears**, following the detected layout and reading order.
Format the transcribed text using **markdown syntax** for better structure and readability:
- Use `#` for main headings, `##` for subheadings, `###` for subsections
- Use `**bold**` for important terms, emphasis, or headings within text
- Use `-` or `*` for bullet lists
- Use `1.`, `2.`, etc. for numbered lists
- Preserve paragraph breaks with blank lines

### Exact Transcription Rules
- Copy all text precisely, preserving:
  - Formatting, punctuation, and diacritics (å, ä, ö, é, ñ, etc.)
  - Capitalization and number formatting
  - Paragraph breaks and line spacing
  - Underscores (_) used for blanks
  - Number formatting and mathematical notation
  - **Do NOT infer or supply missing text. If text is partially obscured, unreadable, \
    or intended as a blank, leave it as underscores
  - **Never replace blanks or questions with possible answers.**
  - **Never attempt to complete, interpret, or explain exercises or examples.**

### Layout and Section Rules
- For multiple **vertical columns**, transcribe *top-to-bottom per column*, \
  inserting: `—-—`
- For **side-by-side exercise blocks** (e.g., "A" and "B"), transcribe *left block first*, \
  then *right block*, inserting: `—-—`
- For boxed or colored sections, mark them clearly: `=== [Section Start: describe if visible] ===
…content…
=== [Section End] ===`
---

## Content Inclusion
Transcribe **all visible text**, including:
- Headings, instructions, and exercises
- Text within boxes, frames, or highlighted areas
- Exercise questions and instructions
- Notes, annotations, and captions
- Word lists and vocabulary
- Page numbers, headers, and footers
- Table content and labels

---

## Special Handling
- For unclear text, use `[unclear]` — never guess.
- Ignore decorative or graphic elements.
- Keep the original language.
- Do not add explanations or commentary.
- Underscores (_) in exercises represent blank spaces for student answers - transcribe as is

---

## Quality Control
- Confirm that **all text areas (columns, blocks, or sections)** were captured.
- Verify **names, numbers, and special characters**.
- Ensure **no text** was omitted from right-side or bottom areas.

---

## Output Format
Return a JSON object with this structure:

```json
{{
"layout_summary": "Brief description of the detected layout",
"transcribed_text": "The complete transcribed text in correct reading order",
"recognition_statistics": {{
  "total_elements": N,
  "successfully_transcribed": X,
  "unclear_uncertain": Y,
  "unable_to_recognize": Z
}}
}}
If no readable text exists, respond with: `{{"error": "Could not recognize text on the page."}}`
Important Notes
- Do not stop after the left column or left exercise block — always check for continuation on the right.
- Be cautious with side-by-side sections labeled A/B or 1–6 vs 7–9.
- If text appears in multiple columns, transcribe left-to-right, top-to-bottom
- Pay special attention to text in blue and light-blue boxes -- it is probably important rules or explanations
- Don't ignore text in light-blue boxes or any colored boxes (blue, dark-blue, etc.)
- Dark boxes often contain critical text content - transcribe ALL text within them exactly as it appears
- NEVER add descriptive text like "[black box with text]" or "[dark area]" - only transcribe the actual readable text
- Do NOT hallucinate or invent text that isn't clearly visible - transcribe only what you can actually read
- Be extremely precise with names, numbers, and exercise content - transcribe EXACTLY as shown, don't modify or guess
- Ignore images, and non-text graphics
- Maintain the original language of the text (don't translate)
+ Do **not** interpret or solve exercises — leave all blanks, questions, and tasks exactly as they appear.
+ If you detect any exercises, quizzes, or fill-in tasks, **transcribe them verbatim** and \
  **do not provide or infer answers under any circumstance**.
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
   - Extract ALL Swedish words and meaningful phrases from the text, including:
     * All nouns (common and proper nouns, except when used as personal names in context)
     * All verbs in any form (infinitives, conjugated forms, past participles)
     * All adjectives and adverbs
     * Phrasal expressions and common collocations
     * Compound words and technical terms
   - INCLUDE words that appear in:
     * The main body text
     * Titles and headings
     * Exercise descriptions and instructions
     * Example sentences
   - EXCLUDE only these categories:
     * Personal names used as names in the text (e.g., "Alfred", "Bertha" when referring to people)
     * The most basic pronouns: jag, du, han, hon, den, det, vi, ni, de, hen
     * The most basic articles when standalone: en, ett
     * The most basic conjunctions when standalone: och, eller, men, att (as conjunction)
     * The most basic prepositions when standalone: i, på, av, till, från, med, för, om
   - IMPORTANT: DO include function words when they are part of meaningful phrases
     (e.g., "gå till" as a phrasal verb, "tycka om" as an expression)
   - DO include all content words, even if they seem basic (e.g., år, dag, stor, god, vara, ha, göra)
   - For each word, identify all distinct forms present in the text (e.g., dog/dö, föddes/födas,
     slutade/sluta, stora/stor)
   - Lowercase all entries except proper nouns and abbreviations
   - Deduplicate identical entries, but preserve different grammatical forms as separate entries
   - For each entry provide:
     * swedish: the word or phrase as it appears in text
     * english: the most contextually appropriate English translation
     * example_phrase: a complete sentence from the source text containing this word.
       If the word appears multiple times, choose the most illustrative example.
       If the example is unclear or unhelpful or non-demonstrative enough, generate a better example.
       After the example sentence, always include its English translation in parentheses.
       The translation is mandatory even if the example is from the source text.
   - Sort all entries alphabetically by the Swedish word
   - Aim for comprehensive vocabulary extraction - a typical textbook page should yield
     50-150+ vocabulary entries depending on text length and density

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
    PromptType.VOCABULARY_BATCH_IMPROVE: PromptTemplate(
        name="Vocabulary Batch Improvement",
        version="1.0.0",
        content="""
You are a Swedish language learning expert. Your task is to provide grammatical information (extra_info)
for a batch of Swedish words/phrases.

WORD/PHRASE LIST:
{word_phrases_list}

For each word/phrase, provide:
- Grammatical information (word form, base form, en/ett classification for nouns, verb forms, etc.)
- Keep it concise and human-readable
- Focus on the most important details for language learners

Return ONLY a JSON object where each key is the Swedish word/phrase and the value is the extra_info string:

{{
    "word_phrase_1": "grammatical details here",
    "word_phrase_2": "grammatical details here"
}}

IMPORTANT:
- Include ALL word_phrases from the input list
- If you cannot determine extra_info for a word, use null as the value
- Keep extra_info concise (e.g., "en-word, noun, base form: ord")
- For nouns: include en/ett classification and base form if different
- For verbs: include verb forms (infinitive, present, past, supine) if relevant
- For adjectives: include comparative forms if relevant
- Don't provide base form if word is already in base form

Return ONLY valid JSON, no additional text or formatting.
""",
        parameters=["word_phrases_list"],
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
