"""
Prompt builder module for managing LLM prompts and responses.

This module provides a centralized, type-safe interface for building prompts
and parsing responses from LLM providers.

Public API:
    - PromptBuilder: Main interface for building prompts
    - ResponseParser: Unified interface for parsing LLM responses
    - PromptType: Enum of supported prompt types
    - ImprovementMode: Enum of vocabulary improvement modes
    - Response validators: Pydantic models for type-safe response handling
"""

from .builder import PromptBuilder
from .parsers import ResponseParser
from .types import ImprovementMode, PromptType
from .validators import (
    AnalysisResponse,
    GrammarFocusResponse,
    OCRResponse,
    RecognitionStatistics,
    SearchNeededResponse,
    VocabularyItemResponse,
    VocabularyResponse,
)

__version__ = "1.0.0"

__all__ = [
    "PromptBuilder",
    "ResponseParser",
    "PromptType",
    "ImprovementMode",
    "OCRResponse",
    "RecognitionStatistics",
    "AnalysisResponse",
    "GrammarFocusResponse",
    "VocabularyItemResponse",
    "SearchNeededResponse",
    "VocabularyResponse",
]
