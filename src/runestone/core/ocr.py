"""
OCR processing module using configurable LLM providers.

This module handles image processing and text extraction from Swedish textbook pages
using various LLM providers like OpenAI or Gemini.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.clients.factory import create_llm_client
from runestone.core.logging_config import get_logger
from runestone.core.exceptions import ImageProcessingError, OCRError
from runestone.core.prompts import OCR_PROMPT


class OCRProcessor:
    """Handles OCR processing using configurable LLM providers."""

    def __init__(
        self,
        settings: Settings,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the OCR processor.

        Args:
            settings: application settings
            client: Pre-configured LLM client (if provided, other params are ignored)
            provider: LLM provider name ("openai" or "gemini")
            api_key: API key for the provider
            model_name: Model name to use
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        if client is not None:
            self.client = client
        else:
            self.client = create_llm_client(
                settings=self.settings,
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                verbose=self.verbose,
            )

    def _load_and_validate_image(self, image_path: Path) -> Image.Image:
        """
        Load and validate an image file.

        Args:
            image_path: Path to the image file

        Returns:
            PIL Image object

        Raises:
            ImageProcessingError: If image cannot be loaded or is invalid
        """
        try:
            image = Image.open(image_path)

            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Check image size (basic validation)
            width, height = image.size
            if width < 100 or height < 100:
                raise ImageProcessingError("Image is too small (minimum 100x100 pixels)")

            if width > 4096 or height > 4096:
                # Resize large images to prevent API issues
                image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
                if self.verbose:
                    self.logger.info(f"Resized large image to {image.size}")

            return image

        except FileNotFoundError:
            raise ImageProcessingError(f"Image file not found: {image_path}")
        except Exception as e:
            raise ImageProcessingError(f"Failed to load image: {str(e)}")

    def _parse_and_analyze_recognition_stats(self, extracted_text: str) -> str:
        """
        Parse JSON response from OCR and analyze recognition quality.

        Args:
            extracted_text: JSON string from OCR response

        Returns:
            Cleaned transcribed text

        Raises:
            OCRError: If recognition percentage is below 90% or JSON parsing fails
        """
        try:
            # Parse JSON response
            response_data = json.loads(extracted_text)

            # Check for error response
            if "error" in response_data:
                raise OCRError(response_data["error"])

            # Extract transcribed text
            transcribed_text = response_data.get("transcribed_text", "").strip()

            # Analyze recognition statistics
            stats = response_data.get("recognition_statistics", {})
            total = stats.get("total_elements", 0)
            success = stats.get("successfully_transcribed", 0)

            if total > 0:
                percentage = (success / total) * 100
                if percentage < 90:
                    raise OCRError(
                        f"OCR recognition percentage below 90%: {percentage:.1f}% ({success}/{total})",
                        details=str(stats),
                    )
            # If total == 0, skip check (assume no text to recognize)

            return transcribed_text

        except json.JSONDecodeError as e:
            raise OCRError(f"Failed to parse OCR response as JSON: {str(e)}")
        except KeyError as e:
            raise OCRError(f"Missing required field in OCR response: {str(e)}")

    def extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract text from a Swedish textbook page image.

        Args:
            image: PIL Image object to process

        Returns:
            Dictionary containing extracted text and metadata

        Raises:
            OCRError: If text extraction fails
        """
        try:
            # Validate image
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Check image size (basic validation)
            width, height = image.size
            if width < 100 or height < 100:
                raise ImageProcessingError("Image is too small (minimum 100x100 pixels)")

            if width > 4096 or height > 4096:
                # Resize large images to prevent API issues
                image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
                if self.verbose:
                    self.logger.info(f"Resized large image to {image.size}")

            # Prepare the prompt for OCR
            ocr_prompt = OCR_PROMPT

            # Use the client for OCR processing
            extracted_text = self.client.extract_text_from_image(image, ocr_prompt)

            # Parse and analyze recognition statistics
            text_part = self._parse_and_analyze_recognition_stats(extracted_text)

            # Check if extracted text is too short
            if len(text_part) < 10:
                raise OCRError("Extracted text is too short - may not be a valid textbook page")

            return {
                "text": text_part,
                "character_count": len(text_part),
            }

        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")
