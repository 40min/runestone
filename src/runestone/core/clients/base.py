"""
Base client interface for LLM providers.

This module defines the abstract base class that all LLM client implementations
must inherit from to ensure consistent interfaces.
"""

from abc import ABC, abstractmethod

from PIL import Image

from runestone.core.logging_config import get_logger


class BaseLLMClient(ABC):
    """Abstract base class for LLM client implementations."""

    def __init__(self, api_key: str, verbose: bool = False):
        """
        Initialize the LLM client.

        Args:
            api_key: API key for the LLM provider
            verbose: Enable verbose logging
        """
        self.logger = get_logger(__name__)
        self.api_key = api_key
        self.verbose = verbose

    @abstractmethod
    def extract_text_from_image(self, image: Image.Image, prompt: str) -> str:
        """
        Extract text from an image using OCR capabilities.

        Args:
            image: PIL Image object
            prompt: OCR prompt for the model

        Returns:
            Extracted text as string

        Raises:
            Exception: If OCR processing fails
        """
        pass

    @abstractmethod
    def analyze_content(self, prompt: str) -> str:
        """
        Analyze content using the LLM.

        Args:
            prompt: Analysis prompt

        Returns:
            Analysis result as string

        Raises:
            Exception: If content analysis fails
        """
        pass

    @abstractmethod
    def search_resources(self, prompt: str) -> str:
        """
        Search for learning resources using the LLM.

        Args:
            prompt: Search prompt

        Returns:
            Search results as string

        Raises:
            Exception: If resource search fails
        """
        pass

    @abstractmethod
    def improve_vocabulary_item(self, prompt: str) -> str:
        """
        Improve a vocabulary item using the LLM.

        Args:
            prompt: Vocabulary improvement prompt

        Returns:
            Improved vocabulary data as string

        Raises:
            Exception: If vocabulary improvement fails
        """
        pass

    @abstractmethod
    def improve_vocabulary_batch(self, prompt: str) -> str:
        """
        Improve multiple vocabulary items in a single batch request.

        Args:
            prompt: Batch vocabulary improvement prompt containing list of words

        Returns:
            JSON string containing word_phrase -> extra_info mappings

        Raises:
            LLMError: If batch improvement fails
        """
        pass

    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the model being used."""
        pass

    @property
    def log_mark(self) -> str:
        """Return the log marker for this client (provider:model)."""
        return f"[{self.provider_name}:{self.model_name}]"
