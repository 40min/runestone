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
from runestone.core.clients.openrouter_client import OpenRouterClient
from runestone.core.exceptions import APIKeyError


def _create_openai_client(settings: Settings, model_name: str | None) -> OpenAIClient:
    """Create an OpenAI LLM client."""
    api_key = settings.openai_api_key
    if not api_key:
        raise APIKeyError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
    if model_name:
        return OpenAIClient(api_key=api_key, model_name=model_name, verbose=settings.verbose)
    else:
        return OpenAIClient(api_key=api_key, verbose=settings.verbose)


def _create_gemini_client(settings: Settings) -> GeminiClient:
    """Create a Gemini LLM client."""
    api_key = settings.gemini_api_key
    if not api_key:
        raise APIKeyError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
    return GeminiClient(api_key=api_key, verbose=settings.verbose)


def _create_openrouter_client(settings: Settings, model_name: str | None) -> OpenRouterClient:
    """Create an OpenRouter LLM client."""
    api_key = settings.openrouter_api_key
    if not api_key:
        raise APIKeyError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
    if model_name:
        return OpenRouterClient(api_key=api_key, model_name=model_name, verbose=settings.verbose)
    else:
        return OpenRouterClient(api_key=api_key, verbose=settings.verbose)


def create_llm_client(
    settings: Settings, provider: Optional[str] = None, model_name: Optional[str] = None
) -> BaseLLMClient:
    """
    Create an LLM client based on centralized configuration.

    Args:
        settings: Centralized application settings
        provider: Optional provider override (defaults to settings.llm_provider)
        model_name: Optional model name override (defaults to settings.llm_model_name)

    Returns:
        Configured LLM client instance

    Raises:
        APIKeyError: If API key is not provided or invalid provider specified
        ValueError: If unsupported provider is specified
    """
    # Prioritize override parameters over settings
    effective_provider = (provider or settings.llm_provider).lower()
    effective_model_name = model_name or settings.llm_model_name

    # Validate provider
    if effective_provider not in get_available_providers():
        raise ValueError(
            f"Unsupported LLM provider: {effective_provider}. "
            f"Supported providers: {', '.join(get_available_providers())}"
        )

    # Create client based on provider
    if effective_provider == "openai":
        return _create_openai_client(settings=settings, model_name=effective_model_name)
    elif effective_provider == "gemini":
        return _create_gemini_client(settings=settings)
    elif effective_provider == "openrouter":
        return _create_openrouter_client(settings=settings, model_name=effective_model_name)

    # This should never be reached due to earlier validation
    raise ValueError(f"Unsupported provider: {effective_provider}")


def get_available_providers() -> list[str]:
    """
    Get list of available LLM providers.

    Returns:
        List of supported provider names
    """
    return ["openai", "gemini", "openrouter"]
