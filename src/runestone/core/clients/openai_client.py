from openai import OpenAI

from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import APIKeyError


class OpenAIClient(BaseLLMClient):
    """OpenAI implementation of the LLM client interface."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", verbose: bool = False):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key
            model_name: Name of the OpenAI model to use (default: gpt-4o-mini)
            verbose: Enable verbose logging
        """
        super().__init__(api_key, verbose)
        self._model_name = model_name
        self._configure_client()

    def _configure_client(self) -> None:
        """Configure OpenAI API client."""
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenAI API: {str(e)}")

    def _call_llm(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 10000) -> any:
        """Call the OpenAI Chat Completion API."""
        return self.client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return self._model_name
