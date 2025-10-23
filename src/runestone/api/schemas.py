"""
Pydantic models for API request/response schemas.

This module defines the data models used for API communication,
ensuring type safety and validation for the Runestone web API.
"""

from typing import List, Optional

from pydantic import BaseModel

from runestone.core.prompt_builder.types import ImprovementMode


class OCRResult(BaseModel):
    """Schema for OCR processing results."""

    text: str
    character_count: int


class GrammarFocus(BaseModel):
    """Schema for grammar focus analysis."""

    topic: str
    explanation: str
    has_explicit_rules: bool
    rules: Optional[str] = None


class VocabularyItem(BaseModel):
    """Schema for individual vocabulary items."""

    swedish: str
    english: str
    example_phrase: Optional[str] = None


class SearchNeeded(BaseModel):
    """Schema for search requirements."""

    should_search: bool
    query_suggestions: List[str]


class ContentAnalysis(BaseModel):
    """Schema for content analysis results."""

    grammar_focus: GrammarFocus
    vocabulary: List[VocabularyItem]
    core_topics: List[str]
    search_needed: SearchNeeded


class AnalysisRequest(BaseModel):
    """Schema for analysis request payload."""

    text: str


class ResourceRequestData(BaseModel):
    """Minimal schema for resource search request data."""

    core_topics: List[str]
    search_needed: SearchNeeded


class ResourceRequest(BaseModel):
    """Schema for resource search request payload."""

    analysis: ResourceRequestData


class ResourceResponse(BaseModel):
    """Schema for resource search response."""

    extra_info: str


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    """Schema for health check responses."""

    status: str
    version: str = "1.0.0"


class VocabularyItemCreate(BaseModel):
    """Schema for creating vocabulary items."""

    word_phrase: str
    translation: str
    example_phrase: Optional[str] = None
    extra_info: Optional[str] = None
    in_learn: bool = True


class VocabularyUpdate(BaseModel):
    """Schema for updating vocabulary items."""

    word_phrase: Optional[str] = None
    translation: Optional[str] = None
    example_phrase: Optional[str] = None
    extra_info: Optional[str] = None
    in_learn: Optional[bool] = None


class VocabularySaveRequest(BaseModel):
    """Schema for saving vocabulary request."""

    items: List[VocabularyItemCreate]
    enrich: bool = True


class Vocabulary(BaseModel):
    """Schema for vocabulary database records."""

    id: int
    user_id: int
    word_phrase: str
    translation: str
    example_phrase: Optional[str] = None
    extra_info: Optional[str] = None
    in_learn: bool = True
    last_learned: Optional[str] = None
    learned_times: int = 0
    created_at: str
    updated_at: str


class VocabularyImproveRequest(BaseModel):
    """Schema for vocabulary improvement request."""

    word_phrase: str
    mode: ImprovementMode = ImprovementMode.EXAMPLE_ONLY


class VocabularyImproveResponse(BaseModel):
    """Schema for vocabulary improvement response."""

    translation: Optional[str] = None
    example_phrase: Optional[str] = None
    extra_info: Optional[str] = None
