"""
Pydantic validators for prompt responses.

This module defines validation schemas for all LLM response types
to ensure type-safe parsing and data integrity.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class RecognitionStatistics(BaseModel):
    """OCR recognition statistics."""

    total_elements: int = Field(ge=0, default=0, description="Total number of text elements detected")
    successfully_transcribed: int = Field(ge=0, default=0, description="Number of successfully transcribed elements")
    unclear_uncertain: int = Field(ge=0, default=0, description="Number of unclear or uncertain elements")
    unable_to_recognize: int = Field(ge=0, default=0, description="Number of elements unable to recognize")


class OCRResponse(BaseModel):
    """Validated OCR response structure."""

    transcribed_text: str = Field(description="The transcribed text from the image")
    recognition_statistics: RecognitionStatistics = Field(description="Statistics about recognition quality")


class GrammarFocusResponse(BaseModel):
    """Grammar focus section of content analysis."""

    has_explicit_rules: bool = Field(description="Whether explicit grammar rules are present")
    topic: str = Field(description="Main grammatical topic")
    rules: Optional[str] = Field(None, description="Grammar rules from the page")
    explanation: str = Field(description="English explanation of the grammar concept")


class VocabularyItemResponse(BaseModel):
    """Individual vocabulary item from content analysis."""

    swedish: str = Field(description="Swedish word or phrase")
    english: str = Field(description="English translation")
    example_phrase: Optional[str] = Field(None, description="Example sentence from source text")


class SearchNeededResponse(BaseModel):
    """Search requirement information."""

    should_search: bool = Field(description="Whether additional resource search is needed")
    query_suggestions: List[str] = Field(default_factory=list, description="Suggested search queries")


class AnalysisResponse(BaseModel):
    """Complete content analysis response."""

    grammar_focus: GrammarFocusResponse = Field(description="Grammar focus information")
    vocabulary: List[VocabularyItemResponse] = Field(default_factory=list, description="Vocabulary items found")
    core_topics: List[str] = Field(default_factory=list, description="Main topics covered")
    search_needed: SearchNeededResponse = Field(description="Search requirements")


class VocabularyResponse(BaseModel):
    """Vocabulary improvement response.

    Fields returned depend on the improvement mode:
    - EXAMPLE_ONLY: only example_phrase is populated
    - EXTRA_INFO_ONLY: only extra_info is populated
    - ALL_FIELDS: all fields are populated
    """

    translation: Optional[str] = Field(None, description="English translation of the Swedish word/phrase")
    example_phrase: Optional[str] = Field(None, description="Natural Swedish sentence using the word in context")
    extra_info: Optional[str] = Field(None, description="Grammatical details (word form, base form, etc.)")
