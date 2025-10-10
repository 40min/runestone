"""
Custom exceptions for the prompt builder module.

This module defines specific exceptions for prompt building and response parsing operations.
"""


class PromptBuilderError(Exception):
    """Base exception for prompt builder module."""

    pass


class TemplateNotFoundError(PromptBuilderError):
    """Raised when a requested template is not found in the registry."""

    pass


class ParameterMissingError(PromptBuilderError):
    """Raised when required parameters are missing for template rendering."""

    pass


class ResponseParseError(PromptBuilderError):
    """Raised when response parsing fails."""

    pass


class ValidationError(PromptBuilderError):
    """Raised when response validation fails."""

    pass
