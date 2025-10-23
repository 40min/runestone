"""
OpenRouter LLM client implementation.

This module provides an OpenRouter-specific implementation of the OpenAIClient
interface, handling OCR and content analysis using OpenRouter's API.
"""

from openai import APIError, OpenAI

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import APIKeyError, LLMError


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

    def improve_vocabulary_batch(self, prompt: str) -> str:
        """
        Improve multiple vocabulary items using OpenRouter in batch.

        Args:
            prompt: Batch vocabulary improvement prompt

        Returns:
            JSON string with batch improvements

        Raises:
            LLMError: If batch improvement fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError(f"No vocabulary batch improvement returned from {self.provider_name}")

            return response.choices[0].message.content.strip()

        except APIError as e:
            raise LLMError(f"OpenRouter API error during vocabulary batch improvement: {str(e)}")
        except Exception as e:
            raise LLMError(f"Vocabulary batch improvement failed: {str(e)}")

    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openrouter"
