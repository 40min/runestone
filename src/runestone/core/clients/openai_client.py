"""
OpenAI LLM client implementation.

This module provides an OpenAI-specific implementation of the BaseLLMClient
interface, handling OCR and content analysis using OpenAI's GPT-4o API.
Uses async httpx for non-blocking HTTP calls.
"""

import base64
import io

from openai import AsyncOpenAI
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
        self._base_url = "https://api.openai.com/v1"
        self._configure_client()

    def _configure_client(self) -> None:
        """Configure OpenAI async client."""
        try:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=getattr(self, "_base_url", None),
                timeout=120.0,
                max_retries=3,
            )
        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenAI client: {str(e)}")

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

    async def extract_text_from_image(self, image: Image.Image, prompt: str) -> str:
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
            self.logger.debug(f"{self.log_mark} Starting OCR processing with model: {self._model_name}")

            # Convert image to base64
            image_b64 = self._image_to_base64(image)

            self.logger.debug(f"{self.log_mark} Sending request to OpenAI API...")

            response = await self._client.chat.completions.create(
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

            extracted_text = response.choices[0].message.content
            if not extracted_text:
                self.logger.error(f"{self.log_mark} No text returned from OpenAI API response")
                raise OCRError("No text returned from OpenAI API")

            extracted_text = extracted_text.strip()
            self.logger.debug(f"{self.log_mark} Extracted text length: {len(extracted_text)} characters")

            # Check for error response
            if "ERROR: Could not recognise text on the page" in extracted_text:
                self.logger.error(f"{self.log_mark} Model returned error: Could not recognise text on the page")
                raise OCRError("Could not recognise text on the page.")

            if len(extracted_text) < 10:
                self.logger.error(f"{self.log_mark} Extracted text too short: {len(extracted_text)} chars")
                raise OCRError("Extracted text is too short - may not be a valid textbook page")

            self.logger.debug(f"{self.log_mark} OCR processing completed successfully")

            return extracted_text

        except OCRError:
            raise
        except Exception as e:
            self.logger.error(f"{self.log_mark} OpenAI API error: {str(e)}")
            raise OCRError(f"OCR processing failed: {str(e)}")

    async def analyze_content(self, prompt: str) -> str:
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
            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMError("No analysis returned from OpenAI")

            return content.strip()

        except Exception as e:
            raise LLMError(f"Content analysis failed: {str(e)}")

    async def search_resources(self, prompt: str) -> str:
        """
        Search for learning resources using OpenAI.

        Args:
            prompt: Search prompt

        Returns:
            Search results as string

        Raises:
            LLMError: If resource search fails
        """
        try:
            self.logger.debug(f"{self.log_mark} Searching for educational resources...")

            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=10000,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMError("No search results returned from OpenAI")

            return content.strip()

        except Exception as e:
            raise LLMError(f"Resource search failed: {str(e)}")

    async def _improve_vocabulary(
        self, prompt: str, no_response_msg: str, api_error_msg: str, general_error_msg: str
    ) -> str:
        """
        Private helper method for vocabulary improvement operations.

        Args:
            prompt: The prompt to send to OpenAI
            no_response_msg: Error message for no response case
            api_error_msg: Error message prefix for API errors
            general_error_msg: Error message prefix for general exceptions

        Returns:
            Improved vocabulary data as string

        Raises:
            LLMError: If the operation fails
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMError(no_response_msg)

            return content.strip()

        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"{api_error_msg}: {str(e)}")

    async def improve_vocabulary_item(self, prompt: str) -> str:
        """
        Improve a vocabulary item using OpenAI.

        Args:
            prompt: Vocabulary improvement prompt

        Returns:
            Improved vocabulary data as string

        Raises:
            LLMError: If vocabulary improvement fails
        """
        return await self._improve_vocabulary(
            prompt,
            f"No vocabulary improvement returned from {self.provider_name}",
            f"{self.provider_name} API error during vocabulary improvement",
            "Vocabulary improvement failed",
        )

    async def improve_vocabulary_batch(self, prompt: str) -> str:
        """
        Improve multiple vocabulary items using OpenAI in batch.

        Args:
            prompt: Batch vocabulary improvement prompt

        Returns:
            JSON string with batch improvements

        Raises:
            LLMError: If batch improvement fails
        """
        return await self._improve_vocabulary(
            prompt,
            f"No vocabulary batch improvement returned from {self.provider_name}",
            f"{self.provider_name} API error during vocabulary batch improvement",
            "Vocabulary batch improvement failed",
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return self._model_name
