"""
Pydantic models for API request/response schemas.

This module defines the data models used for API communication,
ensuring type safety and validation for the Runestone web API.
"""

from typing import List, Optional

from pydantic import BaseModel


class OCRResult(BaseModel):
    """Schema for OCR processing results."""

    text: str
    character_count: int


class GrammarFocus(BaseModel):
    """Schema for grammar focus analysis."""

    topic: str
    explanation: str
    has_explicit_rules: bool


class VocabularyItem(BaseModel):
    """Schema for individual vocabulary items."""

    swedish: str
    english: str


class ContentAnalysis(BaseModel):
    """Schema for content analysis results."""

    grammar_focus: GrammarFocus
    vocabulary: List[VocabularyItem]


class ProcessingResult(BaseModel):
    """Schema for complete processing results."""

    ocr_result: OCRResult
    analysis: ContentAnalysis
    extra_info: Optional[str] = None
    processing_successful: bool = True


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    """Schema for health check responses."""

    status: str
    version: str = "1.0.0"
