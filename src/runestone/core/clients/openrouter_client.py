"""
OpenRouter LLM client implementation.

This module provides an OpenRouter-specific implementation of the OpenAIClient
interface, handling OCR and content analysis using OpenRouter's API.
"""

from openrouter import OpenRouter

from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import APIKeyError


class OpenRouterClient(BaseLLMClient):
    """OpenRouter implementation of the LLM client interface."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", verbose: bool = False):
        """
        Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model_name: Name of the model to use
            verbose: Enable verbose logging
        """
        super().__init__(api_key, verbose)
        self._model_name = model_name
        self._configure_client()

    def _configure_client(self) -> None:
        """Configure OpenRouter API client."""
        try:
            self.client = OpenRouter(api_key=self.api_key)
        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenRouter API: {str(e)}")

    def _call_llm(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 10000) -> any:
        """Call the OpenRouter Chat API via SDK."""
        return self.client.chat.send(
            model=self._model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openrouter"

    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return self._model_name
