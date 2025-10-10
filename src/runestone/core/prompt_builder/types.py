"""
Type definitions for the prompt builder module.

This module defines enums and type aliases used throughout the prompt builder.
"""

from enum import Enum


class PromptType(str, Enum):
    """Supported prompt types for different operations."""

    OCR = "ocr"
    ANALYSIS = "analysis"
    SEARCH = "search"
    VOCABULARY_IMPROVE = "vocabulary_improve"


class ImprovementMode(str, Enum):
    """Mode for vocabulary improvement operations."""

    EXAMPLE_ONLY = "example_only"
    EXTRA_INFO_ONLY = "extra_info_only"
    ALL_FIELDS = "all_fields"
