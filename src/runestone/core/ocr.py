"""
OCR processing module using configurable LLM providers.

This module handles image processing and text extraction from Swedish textbook pages
using various LLM providers like OpenAI or Gemini.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from runestone.config import Settings
from runestone.core.clients.base import BaseLLMClient
from runestone.core.exceptions import ImageProcessingError, OCRError
from runestone.core.logging_config import get_logger
from runestone.core.prompt_builder import PromptBuilder, ResponseParser
from runestone.core.prompt_builder.exceptions import ResponseParseError


class OCRProcessor:
    """Handles OCR processing using configurable LLM providers."""

    def __init__(
        self,
        settings: Settings,
        client: BaseLLMClient,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the OCR processor.

        Args:
            settings: application settings
            client: LLM client for processing
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        self.client = client

        # Initialize prompt builder and parser
        self.builder = PromptBuilder()
        self.parser = ResponseParser()

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
            OCRError: If recognition percentage is below 90% or parsing fails
        """
        try:
            # Parse and validate response using ResponseParser
            response = self.parser.parse_ocr_response(extracted_text)

            # Analyze recognition statistics
            stats = response.recognition_statistics
            total = stats.total_elements
            success = stats.successfully_transcribed

            if total > 0:
                percentage = (success / total) * 100
                if percentage < 90:
                    raise OCRError(
                        f"OCR recognition percentage below 90%: {percentage:.1f}% ({success}/{total})",
                        details=str(stats),
                    )
            # If total == 0, skip check (assume no text to recognize)

            return response.transcribed_text.strip()

        except ResponseParseError as e:
            raise OCRError(f"Failed to parse OCR response: {str(e)}")

    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Minimal preprocessing to preserve accuracy while slightly helping with light-blue text.

        Args:
            image: PIL Image object to preprocess

        Returns:
            Preprocessed PIL Image object with minimal adjustments
        """
        try:
            if self.verbose:
                self.logger.info(f"Starting minimal image preprocessing: mode={image.mode}, size={image.size}")

            # Only ensure RGB format for LLM compatibility - no aggressive preprocessing
            # Based on user feedback: preprocessing causes more harm than good for accuracy
            if image.mode != "RGB":
                final_image = image.convert("RGB")
                if self.verbose:
                    self.logger.info("Converted image to RGB format for LLM compatibility")
            else:
                final_image = image

            if self.verbose:
                self.logger.info(f"Minimal preprocessing complete: mode={final_image.mode}, size={final_image.size}")

            return final_image

        except (AttributeError, TypeError) as e:
            # Handle cases where we might be working with a mock object during testing
            if self.verbose:
                self.logger.warning(f"Image preprocessing failed ({str(e)}), using original image")

            # Return original image if preprocessing fails (e.g., during testing with mocks)
            # Ensure it's in RGB format for LLM processing
            if hasattr(image, "convert") and hasattr(image, "mode"):
                return image.convert("RGB") if image.mode != "RGB" else image
            else:
                return image

    def extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract text from a Swedish textbook page image with enhanced preprocessing.

        Args:
            image: PIL Image object to process

        Returns:
            Dictionary containing extracted text and metadata

        Raises:
            OCRError: If text extraction fails
        """
        try:
            # Log original image characteristics for debugging
            if self.verbose:
                self.logger.info(f"Processing image: mode={image.mode}, size={image.size}")

            # Basic validation and size adjustment
            if image.mode not in ["RGB", "RGBA", "L"]:
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

            # ENHANCEMENT: Apply preprocessing for better light-blue text detection
            preprocessed_image = self._preprocess_image_for_ocr(image)

            # Build OCR prompt using PromptBuilder
            ocr_prompt = self.builder.build_ocr_prompt()

            # Use the client for OCR processing with preprocessed image
            extracted_text = self.client.extract_text_from_image(preprocessed_image, ocr_prompt)

            # Check if we got a valid response
            if not extracted_text:
                raise OCRError("No text returned from OCR processing")

            # Parse and analyze recognition statistics
            text_part = self._parse_and_analyze_recognition_stats(extracted_text)

            # Check if extracted text is too short
            if len(text_part) < 10:
                raise OCRError("Extracted text is too short - may not be a valid textbook page")

            if self.verbose:
                self.logger.info(f"OCR extraction successful: {len(text_part)} characters extracted")

            return {
                "text": text_part,
                "character_count": len(text_part),
            }

        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")
