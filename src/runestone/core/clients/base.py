import base64
import io
from abc import ABC, abstractmethod

from PIL import Image

from runestone.core.exceptions import LLMError, OCRError
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
    def _call_llm(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 10000) -> any:
        """
        Call the specific LLM API.

        Args:
            messages: List of message dictionaries
            temperature: Model temperature
            max_tokens: Maximum tokens to generate

        Returns:
            API response object
        """
        pass

    def _get_content_from_response(self, response: any) -> str:
        """
        Standard content extraction from response.

        Args:
            response: API response object

        Returns:
            Extracted content string
        """
        if not response.choices or not response.choices[0].message.content:
            return ""
        return response.choices[0].message.content.strip()

    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string.

        Args:
            image: PIL Image object

        Returns:
            Base64 encoded image string
        """
        buffer = io.BytesIO()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def extract_text_from_image(self, image: Image.Image, prompt: str) -> str:
        """
        Extract text from an image using OCR capabilities.
        """
        try:
            self.logger.debug(f"{self.log_mark} Starting OCR processing with model: {self.model_name}")

            image_b64 = self._image_to_base64(image)

            messages = [
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
            ]

            response = self._call_llm(messages, temperature=0.1)
            extracted_text = self._get_content_from_response(response)

            if not extracted_text:
                self.logger.error(f"{self.log_mark} No text returned from API response")
                raise OCRError(f"No text returned from {self.provider_name} API")

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
            self.logger.error(f"{self.log_mark} OCR processing failed: {str(e)}")
            raise OCRError(f"OCR processing failed: {type(e).__name__}: {str(e)}")

    def analyze_content(self, prompt: str) -> str:
        """Analyze content using the LLM."""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self._call_llm(messages, temperature=0.1)
            content = self._get_content_from_response(response)

            if not content:
                raise LLMError(f"No analysis returned from {self.provider_name}")

            return content
        except Exception as e:
            raise LLMError(f"Content analysis failed: {str(e)}")

    def search_resources(self, prompt: str) -> str:
        """Search for learning resources using the LLM."""
        try:
            self.logger.debug(f"{self.log_mark} Searching for educational resources...")
            messages = [{"role": "user", "content": prompt}]
            response = self._call_llm(messages, temperature=0.3)
            content = self._get_content_from_response(response)

            if not content:
                raise LLMError(f"No search results returned from {self.provider_name}")

            return content
        except Exception as e:
            raise LLMError(f"Resource search failed: {str(e)}")

    def _improve_vocabulary(self, prompt: str, no_response_msg: str, general_error_msg: str) -> str:
        """Private helper method for vocabulary improvement operations."""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self._call_llm(messages, temperature=0.1)
            content = self._get_content_from_response(response)

            if not content:
                raise LLMError(no_response_msg)

            return content
        except Exception as e:
            raise LLMError(f"{general_error_msg}: {str(e)}")

    def improve_vocabulary_item(self, prompt: str) -> str:
        """Improve a vocabulary item using the LLM."""
        return self._improve_vocabulary(
            prompt,
            f"No vocabulary improvement returned from {self.provider_name}",
            "Vocabulary improvement failed",
        )

    def improve_vocabulary_batch(self, prompt: str) -> str:
        """Improve multiple vocabulary items in a single batch request."""
        return self._improve_vocabulary(
            prompt,
            f"No vocabulary batch improvement returned from {self.provider_name}",
            "Vocabulary batch improvement failed",
        )

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

    @property
    def log_mark(self) -> str:
        """Return the log marker for this client (provider:model)."""
        return f"[{self.provider_name}:{self.model_name}]"
