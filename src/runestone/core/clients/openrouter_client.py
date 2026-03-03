"""
OpenRouter LLM client implementation.

This module provides an OpenRouter-specific implementation of the OpenAIClient
interface, handling OCR and content analysis using OpenRouter's API.
Uses async httpx for non-blocking HTTP calls.
"""

from openai import AsyncOpenAI, AuthenticationError

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import APIKeyError


class OpenRouterClient(OpenAIClient):
    """OpenRouter implementation of the LLM client interface."""

    def _configure_client(self) -> None:
        """Configure OpenRouter client using OpenAI SDK."""
        try:

            self._base_url = "https://openrouter.ai/api/v1"
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self._base_url,
                default_headers={
                    "HTTP-Referer": "https://runestone.app",
                    "X-Title": "Runestone",
                },
                timeout=120.0,
            )
        except (AuthenticationError, APIKeyError) as e:
            raise APIKeyError(f"OpenRouter authentication failed: {str(e)}")
        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenRouter API ({type(e).__name__}): {str(e)}")

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openrouter"
