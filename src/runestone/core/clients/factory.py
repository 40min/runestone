"""
Client factory for creating LLM clients based on configuration.

This module provides a factory function to create the appropriate LLM client
based on environment variables and configuration.
"""

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.gemini_client import GeminiClient
from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import APIKeyError


def _create_openai_client(settings: Settings, model_name: str | None, verbose: bool) -> OpenAIClient:
    """Create an OpenAI LLM client."""
    api_key = settings.openai_api_key
    if not api_key:
        raise APIKeyError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
    if model_name:
        return OpenAIClient(api_key=api_key, model_name=model_name, verbose=verbose)
    else:
        return OpenAIClient(api_key=api_key, verbose=verbose)


def _create_gemini_client(settings: Settings, verbose: bool) -> GeminiClient:
    """Create a Gemini LLM client."""
    api_key = settings.gemini_api_key
    if not api_key:
        raise APIKeyError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
    return GeminiClient(api_key=api_key, verbose=verbose)


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """
    Create an LLM client based on centralized configuration.

    Args:
        settings: Centralized application settings

    Returns:
        Configured LLM client instance

    Raises:
        APIKeyError: If API key is not provided or invalid provider specified
        ValueError: If unsupported provider is specified
    """
    provider = settings.llm_provider.lower()
    verbose = settings.verbose

    # Validate provider
    if provider not in get_available_providers():
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported providers: openai, gemini")

    # Create client
    if provider == "openai":
        return _create_openai_client(settings=settings, model_name=settings.llm_model_name, verbose=verbose)
    elif provider == "gemini":
        return _create_gemini_client(settings=settings, verbose=verbose)

    # This should never be reached due to earlier validation
    raise ValueError(f"Unsupported provider: {provider}")


def get_available_providers() -> list[str]:
    """
    Get list of available LLM providers.

    Returns:
        List of supported provider names
    """
    return ["openai", "gemini"]
