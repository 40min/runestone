"""
Client factory for creating LLM clients based on configuration.

This module provides a factory function to create the appropriate LLM client
based on environment variables and configuration.
"""

import os
from typing import Optional

from ..exceptions import APIKeyError
from .base import BaseLLMClient
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient


def create_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    verbose: bool = False,
) -> BaseLLMClient:
    """
    Create an LLM client based on configuration.

    Args:
        provider: LLM provider ("openai" or "gemini"). If None, uses LLM_PROVIDER env var or defaults to "openai"
        api_key: API key for the provider. If None, uses provider-specific env vars
        model_name: Model name to use. If None, uses defaults
        verbose: Enable verbose logging

    Returns:
        Configured LLM client instance

    Raises:
        APIKeyError: If API key is not provided or invalid provider specified
        ValueError: If unsupported provider is specified
    """
    # Determine provider
    provider = provider or os.getenv("LLM_PROVIDER", "openai")
    provider = provider.lower()

    # Validate provider
    if provider not in ["openai", "gemini"]:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported providers: openai, gemini")

    # Get API key
    if api_key is None:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise APIKeyError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
                )
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise APIKeyError(
                    "Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter."
                )

    # Create client
    if provider == "openai":
        if model_name is None:
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAIClient(api_key=api_key, model_name=model_name, verbose=verbose)

    elif provider == "gemini":
        # Gemini client doesn't need model_name parameter (uses fixed model)
        return GeminiClient(api_key=api_key, verbose=verbose)

    # This should never be reached due to earlier validation
    raise ValueError(f"Unsupported provider: {provider}")


def get_available_providers() -> list[str]:
    """
    Get list of available LLM providers.

    Returns:
        List of supported provider names
    """
    return ["openai", "gemini"]


def get_default_provider() -> str:
    """
    Get the default LLM provider.

    Returns:
        Default provider name
    """
    return "openai"
