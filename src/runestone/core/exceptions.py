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


class VocabularyItemExists(RunestoneError):
    """Raised when attempting to create or update a vocabulary item with a duplicate word_phrase."""


class VocabularyOperationError(RunestoneError):
    """Base exception for vocabulary operations."""

    pass


class WordNotFoundError(VocabularyOperationError):
    """Raised when a word is not found in user's vocabulary."""

    def __init__(self, word_phrase: str, username: str):
        self.word_phrase = word_phrase
        self.username = username
        super().__init__(
            message=f"Word '{word_phrase}' not found",
            details=f"User '{username}' does not have '{word_phrase}' in vocabulary",
        )


class WordNotInSelectionError(VocabularyOperationError):
    """Raised when a word is not in today's daily selection."""

    def __init__(self, word_phrase: str):
        self.word_phrase = word_phrase
        super().__init__(message=f"Word '{word_phrase}' not in today's selection")

    pass
