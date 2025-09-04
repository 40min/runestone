"""
Base client interface for LLM providers.

This module defines the abstract base class that all LLM client implementations
must inherit from to ensure consistent interfaces.
"""

from abc import ABC, abstractmethod

from PIL import Image
from rich.console import Console


class BaseLLMClient(ABC):
    """Abstract base class for LLM client implementations."""

    def __init__(self, console: Console, api_key: str, verbose: bool = False):
        """
        Initialize the LLM client.

        Args:
            console: Rich Console instance for output
            api_key: API key for the LLM provider
            verbose: Enable verbose logging
        """
        self.console = console
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

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the model being used."""
        pass
