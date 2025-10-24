"""
OpenRouter LLM client implementation.

This module provides an OpenRouter-specific implementation of the OpenAIClient
interface, handling OCR and content analysis using OpenRouter's API.
"""

from openai import OpenAI

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import APIKeyError


class OpenRouterClient(OpenAIClient):
    """OpenRouter implementation of the LLM client interface."""

    def _configure_client(self) -> None:
        """Configure OpenRouter API client."""
        try:
            self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")

            # Test the client with a simple request to ensure it's properly configured
            # We'll do this lazily in the first actual request to avoid unnecessary costs

        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenRouter API: {str(e)}")

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openrouter"
