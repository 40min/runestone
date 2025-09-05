"""
OpenAI LLM client implementation.

This module provides an OpenAI-specific implementation of the BaseLLMClient
interface, handling OCR and content analysis using OpenAI's GPT-4o API.
"""

import base64
import io

from openai import OpenAI
from PIL import Image

from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import APIKeyError, LLMError, OCRError


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

            # Test the client with a simple request to ensure it's properly configured
            # We'll do this lazily in the first actual request to avoid unnecessary costs

        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenAI API: {str(e)}")

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string for OpenAI API.

        Args:
            image: PIL Image object

        Returns:
            Base64 encoded image string
        """
        buffer = io.BytesIO()
        # Convert to RGB if not already
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def extract_text_from_image(self, image: Image.Image, prompt: str) -> str:
        """
        Extract text from an image using OpenAI Vision API.

        Args:
            image: PIL Image object
            prompt: OCR prompt for the model

        Returns:
            Extracted text as string

        Raises:
            OCRError: If OCR processing fails
        """
        try:
            if self.verbose:
                self.logger.info("Sending image to OpenAI for OCR processing...")

            # Convert image to base64
            image_b64 = self._image_to_base64(image)

            response = self.client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=10000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                raise OCRError("No text returned from OpenAI API")

            extracted_text = response.choices[0].message.content.strip()

            # Check for error response
            if "ERROR: Could not recognise text on the page" in extracted_text:
                raise OCRError("Could not recognise text on the page.")

            if len(extracted_text) < 10:
                raise OCRError("Extracted text is too short - may not be a valid textbook page")

            return extracted_text

        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")

    def analyze_content(self, prompt: str) -> str:
        """
        Analyze content using OpenAI.

        Args:
            prompt: Analysis prompt

        Returns:
            Analysis result as string

        Raises:
            LLMError: If content analysis fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError("No analysis returned from OpenAI")

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise LLMError(f"Content analysis failed: {str(e)}")

    def search_resources(self, prompt: str) -> str:
        """
        Search for learning resources using OpenAI with web search capabilities.

        Args:
            prompt: Search prompt

        Returns:
            Search results as string

        Raises:
            LLMError: If resource search fails
        """
        try:
            if self.verbose:
                self.logger.info("Searching for educational resources with OpenAI...")

            response = self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError("No search results returned from OpenAI")

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise LLMError(f"Resource search failed: {str(e)}")

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return self._model_name
