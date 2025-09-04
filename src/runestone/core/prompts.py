"""
Prompt templates for OCR and other processing tasks.

This module contains reusable prompt templates used throughout the application.
"""

OCR_PROMPT = """
You are an expert OCR transcription assistant. Your task is to accurately transcribe all readable text from the provided image.

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
Provide the transcribed text followed by recognition statistics.

If no readable text exists, respond with:
ERROR: Could not recognize text on the page.

End your transcription with:
```
---
Recognition Statistics:
- Total text elements identified: N
- Successfully transcribed: X
- Unclear/uncertain: Y
- Unable to recognize: Z
---
```

## Important Notes:
- Ignore purely decorative elements, images, and non-text graphics
- Focus on text content only, not visual layout descriptions
- If text appears in multiple columns, transcribe left-to-right, top-to-bottom
- Maintain the original language of the text (don't translate)
"""

ANALYSIS_PROMPT_TEMPLATE = """
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
        "explanation": "English explanation of the grammar rule or pattern"
    }},
    "vocabulary": [
        {{
            "swedish": "Swedish word or phrase",
            "english": "English translation"
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
   - Set has_explicit_rules to true if there's a clear grammar rule box/section
   - Set has_explicit_rules to false if you need to infer the grammar from exercises
   - Provide a clear English explanation of the grammatical concept

2. For vocabulary:
   - Extract key Swedish words, phrases, and important terms
   - Prioritize nouns, verbs, adjectives, and useful phrases
   - Provide accurate English translations
   - Include 10-20 most important items

3. For core_topics:
   - Identify 2-4 main learning topics from this page
   - Use clear, descriptive terms

4. For search_needed:
	- Set should_search = true if the provided page lacks grammar explanations and only contains exercises, examples, or incomplete information.
	- If should_search = true, generate a list of specific and targeted search queries that would help find reliable grammar explanations for the identified topic(s).
	- Queries should be concise, precise, and focus on the exact grammar concept(s) missing from the resource.
	- If explanations are already sufficient, set should_search = false and do not generate queries.

Return ONLY valid JSON, no additional text or formatting.
"""

SEARCH_PROMPT_TEMPLATE = """
You have web search capabilities. Search the web for educational material related to Swedish language learning.

Core topics: {core_topics}
Additional suggestions: {query_suggestions}

Instructions:
- Search the web for relevant, high-quality educational resources.
- Summarize findings into a single structured text, grouped by topic.
- For each topic, give 2–4 concise bullet points with the most useful rules, explanations, or examples.
- Keep the text readable and compact (avoid long sections or repeated titles).
- Prioritize reliable sources such as:
  - svenska.se
  - clozemaster.com/blog/
  - worddive.com/en/grammar/
  - kielibuusti.fi/en/learn-swedish/
  - swedishpod101.com/blog/

Return only the structured educational text.

Format:
- Format the summary in plain text, not Markdown.
- Use emojis for section headers and bullets (e.g., 📌, ❓, 📖, 💡).
- Keep explanations concise and structured with short lines.
- Do not use symbols like **bold**, # headers, or markdown tables.
"""