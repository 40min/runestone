"""
OpenRouter LLM client implementation.

This module provides an OpenRouter-specific implementation of the OpenAIClient
interface, handling OCR and content analysis using OpenRouter's API.
"""

from openrouter import OpenRouter

from runestone.core.clients.openai_client import OpenAIClient
from runestone.core.exceptions import APIKeyError, LLMError, OCRError


class OpenRouterClient(OpenAIClient):
    """OpenRouter implementation of the LLM client interface."""

    def _configure_client(self) -> None:
        """Configure OpenRouter API client."""
        try:
            self.client = OpenRouter(api_key=self.api_key)

            # Test the client with a simple request to ensure it's properly configured
            # We'll do this lazily in the first actual request to avoid unnecessary costs

        except Exception as e:
            raise APIKeyError(f"Failed to configure OpenRouter API: {str(e)}")

    def extract_text_from_image(self, image, prompt: str) -> str:
        """
        Extract text from an image using OpenRouter.

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
            self.logger.debug(f"{self.log_mark} Converting image to base64...")
            image_b64 = self._image_to_base64(image)

            self.logger.debug(f"{self.log_mark} Sending request to OpenRouter API via SDK...")
            response = self.client.chat.send(
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
                                },
                            },
                        ],
                    }
                ],
                max_tokens=10000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                self.logger.error(f"{self.log_mark} No text returned from OpenRouter API response")
                raise OCRError("No text returned from OpenRouter API")

            extracted_text = response.choices[0].message.content.strip()

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
            self.logger.error(f"{self.log_mark} Unexpected error type: {type(e).__name__}")
            self.logger.error(f"{self.log_mark} Error message: {str(e)}")
            raise OCRError(f"OCR processing failed: {type(e).__name__}: {str(e)}")

    def analyze_content(self, prompt: str) -> str:
        """
        Analyze content using OpenRouter.

        Args:
            prompt: Analysis prompt

        Returns:
            Analysis result as string

        Raises:
            LLMError: If content analysis fails
        """
        try:
            response = self.client.chat.send(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError("No analysis returned from OpenRouter")

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise LLMError(f"Content analysis failed: {str(e)}")

    def search_resources(self, prompt: str) -> str:
        """
        Search for learning resources using OpenRouter.

        Args:
            prompt: Search prompt

        Returns:
            Search results as string

        Raises:
            LLMError: If resource search fails
        """
        try:
            self.logger.debug(f"{self.log_mark} Searching for educational resources...")

            response = self.client.chat.send(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.3,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError("No search results returned from OpenRouter")

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise LLMError(f"Resource search failed: {str(e)}")

    def _improve_vocabulary(self, prompt: str, no_response_msg: str, api_error_msg: str, general_error_msg: str) -> str:
        """
        Private helper method for vocabulary improvement operations.

        Args:
            prompt: The prompt to send to OpenRouter
            no_response_msg: Error message for no response case
            api_error_msg: Error message prefix for API errors (unused, kept for signature match if applicable)
            general_error_msg: Error message prefix for general exceptions

        Returns:
            Improved vocabulary data as string

        Raises:
            LLMError: If the operation fails
        """
        try:
            response = self.client.chat.send(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10000,
                temperature=0.1,
            )

            if not response.choices or not response.choices[0].message.content:
                raise LLMError(no_response_msg)

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise LLMError(f"{general_error_msg}: {str(e)}")

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "openrouter"
