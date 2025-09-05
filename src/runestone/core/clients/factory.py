"""
Client factory for creating LLM clients based on configuration.

This module provides a factory function to create the appropriate LLM client
based on environment variables and configuration.
"""

from typing import Optional

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.gemini_client import GeminiClient
from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.logging_config import get_logger
from runestone.core.exceptions import APIKeyError


def create_llm_client(
    settings: Settings,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    verbose: Optional[bool] = None,
) -> BaseLLMClient:
    """
    Create an LLM client based on centralized configuration.

    Args:
        settings: Centralized application settings
        provider: LLM provider ("openai" or "gemini"). If None, uses settings.llm_provider
        api_key: API key for the provider. If None, uses provider-specific settings
        model_name: Model name to use. If None, uses provider defaults from settings
        verbose: Enable verbose logging. If None, uses settings.verbose

    Returns:
        Configured LLM client instance

    Raises:
        APIKeyError: If API key is not provided or invalid provider specified
        ValueError: If unsupported provider is specified
    """
    logger = get_logger(__name__)

    # Use settings values as defaults, but allow overrides
    provider = provider or settings.llm_provider
    provider = provider.lower()
    verbose = verbose if verbose is not None else settings.verbose

    # Validate provider
    if provider not in ["openai", "gemini"]:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported providers: openai, gemini")

    # Get API key from settings or parameter
    if api_key is None:
        if provider == "openai":
            api_key = settings.openai_api_key
            if not api_key:
                raise APIKeyError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
                )
        elif provider == "gemini":
            api_key = settings.gemini_api_key
            if not api_key:
                raise APIKeyError(
                    "Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter."
                )

    # Create client
    if provider == "openai":
        model_name = model_name or settings.openai_model
        return OpenAIClient(api_key=str(api_key), model_name=model_name, verbose=verbose)

    elif provider == "gemini":
        # Gemini client doesn't need model_name parameter (uses fixed model)
        return GeminiClient(api_key=str(api_key), verbose=verbose)

    # This should never be reached due to earlier validation
    raise ValueError(f"Unsupported provider: {provider}")


def get_available_providers() -> list[str]:
    """
    Get list of available LLM providers.

    Returns:
        List of supported provider names
    """
    return ["openai", "gemini"]
