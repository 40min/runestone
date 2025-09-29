"""
Custom exceptions for state management operations.
"""


class StateManagerError(Exception):
    """Base exception for all state manager related errors."""

    pass


class StateFileError(StateManagerError):
    """Base exception for state file operations."""

    pass


class StateCorruptionError(StateFileError):
    """Raised when state file is corrupted or has invalid structure."""

    pass


class StateAccessError(StateFileError):
    """Raised when state file cannot be accessed or created."""

    pass


class UserStateError(StateManagerError):
    """Base exception for user-related state operations."""

    pass
