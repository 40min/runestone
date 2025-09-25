"""
Custom exceptions for Runestone.

This module defines all custom exception types used throughout the application.
"""


class RunestoneError(Exception):
    """Base exception class for all Runestone-specific errors."""

    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class OCRError(RunestoneError):
    """Raised when OCR processing fails."""

    pass


class LLMError(RunestoneError):
    """Raised when LLM processing fails."""

    pass


class SearchError(RunestoneError):
    """Raised when web search functionality fails."""

    pass


class ImageProcessingError(RunestoneError):
    """Raised when image processing fails."""

    pass


class APIKeyError(RunestoneError):
    """Raised when API key is invalid or missing."""

    pass


class ContentAnalysisError(RunestoneError):
    """Raised when content analysis fails."""

    pass


class UserNotAuthorised(RunestoneError):
    """Raised when attempting to update a non-existing user."""

    pass
