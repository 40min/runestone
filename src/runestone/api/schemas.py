"""
Pydantic models for API request/response schemas.

This module serves as the API layer's schema facade, re-exporting
unified schemas from the core layer and defining API-specific models.
This provides a stable API contract and encapsulates internal schema organization.
"""

import json
from typing import Any, Optional

# This provides a stable API contract and encapsulates internal schema organization
from pydantic import BaseModel, Field, field_validator

from runestone.constants import VOCABULARY_PRIORITY_DEFAULT, VOCABULARY_PRIORITY_HIGH, VOCABULARY_PRIORITY_LOW
from runestone.core.prompt_builder.types import ImprovementMode
from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, VocabularyItem
from runestone.schemas.ocr import OCRResult, RecognitionStatistics

# Define the public API contract
__all__ = [
    # Unified schemas (re-exported)
    "ContentAnalysis",
    "GrammarFocus",
    "VocabularyItem",
    "OCRResult",
    "RecognitionStatistics",
    # API-specific request/response models
    "AnalysisRequest",
    "ErrorResponse",
    "HealthResponse",
    "VocabularyItemCreate",
    "VocabularyUpdate",
    "VocabularySaveRequest",
    "Vocabulary",
    "VocabularyImproveRequest",
    "VocabularyImproveResponse",
    "CheatsheetInfo",
    "CheatsheetContent",
    "VocabularyStatsResponse",
    "UserProfileResponse",
    "UserProfileUpdate",
]


class AnalysisRequest(BaseModel):
    """Schema for analysis request payload."""

    text: str


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
    priority_learn: int = Field(
        default=VOCABULARY_PRIORITY_DEFAULT, ge=VOCABULARY_PRIORITY_HIGH, le=VOCABULARY_PRIORITY_LOW
    )

    @field_validator("priority_learn", mode="before")
    @classmethod
    def reject_boolean_priority_learn(cls, v: Any) -> Any:
        """Reject legacy boolean payloads to avoid silent bool->int coercion."""
        if isinstance(v, bool):
            raise ValueError("priority_learn must be an integer between 0 and 9")
        return v


class VocabularyUpdate(BaseModel):
    """Schema for updating vocabulary items."""

    word_phrase: Optional[str] = None
    translation: Optional[str] = None
    example_phrase: Optional[str] = None
    extra_info: Optional[str] = None
    in_learn: Optional[bool] = None
    priority_learn: Optional[int] = Field(default=None, ge=VOCABULARY_PRIORITY_HIGH, le=VOCABULARY_PRIORITY_LOW)

    @field_validator("priority_learn", mode="before")
    @classmethod
    def reject_boolean_priority_learn(cls, v: Any) -> Any:
        """Reject legacy boolean payloads to avoid silent bool->int coercion."""
        if isinstance(v, bool):
            raise ValueError("priority_learn must be an integer between 0 and 9")
        return v


class VocabularySaveRequest(BaseModel):
    """Schema for saving vocabulary request."""

    items: list[VocabularyItemCreate]
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
    priority_learn: int = Field(
        default=VOCABULARY_PRIORITY_DEFAULT, ge=VOCABULARY_PRIORITY_HIGH, le=VOCABULARY_PRIORITY_LOW
    )
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


class CheatsheetInfo(BaseModel):
    """Schema for cheatsheet information."""

    filename: str
    title: str
    category: str


class CheatsheetContent(BaseModel):
    """Schema for cheatsheet content."""

    content: str


class VocabularyStatsResponse(BaseModel):
    """Schema for active vocabulary statistics shown in the Vocabulary tab."""

    words_in_learn_count: int
    words_skipped_count: int
    overall_words_count: int
    words_prioritized_count: int


class UserProfileResponse(BaseModel):
    """Schema for user profile response."""

    id: int
    email: str
    name: str
    surname: Optional[str] = None
    mother_tongue: Optional[str] = None
    timezone: str
    pages_recognised_count: int
    # Agent memory fields
    personal_info: Optional[dict] = None
    areas_to_improve: Optional[dict] = None
    knowledge_strengths: Optional[dict] = None
    created_at: str
    updated_at: str


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""

    name: Optional[str] = None
    surname: Optional[str] = None
    mother_tongue: Optional[str] = None
    timezone: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    # Agent memory fields (input as dict, serialized to JSON string)
    personal_info: Optional[dict[str, Any] | str] = None
    areas_to_improve: Optional[dict[str, Any] | str] = None
    knowledge_strengths: Optional[dict[str, Any] | str] = None

    @field_validator("personal_info", "areas_to_improve", "knowledge_strengths", mode="before")
    @classmethod
    def validate_memory_fields(cls, v: Optional[dict[str, Any] | str]) -> Optional[str]:
        """Validate that memory fields are dicts and serialize to JSON string."""
        if v is None:
            return None
        if isinstance(v, str):
            # Already a string (e.g. from tests or prior serialization), check if it's valid JSON
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError as e:
                raise ValueError("Provided string is not valid JSON.") from e
        if not isinstance(v, dict):
            raise ValueError("Must be a valid JSON object (dictionary)")
        return json.dumps(v)


class LoginRequest(BaseModel):
    email: str
    password: str
