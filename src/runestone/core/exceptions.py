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


class TelegramUsernameConflictError(RunestoneError):
    """Raised when one Telegram username resolves to multiple users."""

    def __init__(self, username: str):
        super().__init__(
            message="Telegram username is linked to multiple Runestone accounts",
            details=f"Normalized username '{username}' matched multiple users",
        )


class RecallOperationError(RunestoneError):
    """Base exception for recall workflow failures."""


class RecallStateNotFoundError(RecallOperationError):
    """Raised when a command requires recall state that does not exist."""

    def __init__(self, user_id: int):
        super().__init__(
            message="Recall state not found",
            details=f"User {user_id} has no persisted recall state",
        )


class WordNotFoundError(VocabularyOperationError):
    """Raised when a word is not found in user's vocabulary."""

    def __init__(self, word_phrase: str, username: str):
        self.word_phrase = word_phrase
        self.username = username
        super().__init__(
            message=f"Word '{word_phrase}' not found",
            details=f"User '{username}' does not have '{word_phrase}' in vocabulary",
        )


class WordNotInSelectionError(RecallOperationError):
    """Raised when a word is not in today's daily selection."""

    def __init__(self, word_phrase: str):
        self.word_phrase = word_phrase
        super().__init__(message=f"Word '{word_phrase}' not in today's selection")


class UserNotFoundError(ValueError):
    """Raised when a user is not found."""

    pass


class PermissionDeniedError(ValueError):
    """Raised when a user lacks permission to perform an action."""

    pass


class MemoryItemNotFoundError(ValueError):
    """Raised when a memory item is not found."""

    pass
