"""
OCR processing module using configurable LLM providers.

This module handles image processing and text extraction from Swedish textbook pages
using various LLM providers like OpenAI or Gemini.
"""

import base64
import io
import time
from pathlib import Path
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from PIL import Image

from runestone.config import Settings
from runestone.core.exceptions import ImageProcessingError, OCRError
from runestone.core.logging_config import get_logger
from runestone.core.prompt_builder.builder import PromptBuilder
from runestone.core.prompt_builder.exceptions import ResponseParseError
from runestone.core.prompt_builder.parsers import ResponseParser
from runestone.core.service_llm import extract_message_text
from runestone.schemas.ocr import OCRResult


class OCRProcessor:
    """Handles OCR processing using configurable LLM providers."""

    def __init__(
        self,
        settings: Settings,
        model: BaseChatModel,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the OCR processor.

        Args:
            settings: application settings
            model: LangChain chat model for processing
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        self.model = model

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

            return image

        except FileNotFoundError:
            raise ImageProcessingError(f"Image file not found: {image_path}")
        except Exception as e:
            raise ImageProcessingError(f"Failed to load image: {str(e)}")

    def _parse_and_analyze_recognition_stats(self, extracted_text: str) -> OCRResult:
        """
        Parse JSON response from OCR and analyze recognition quality.

        Args:
            extracted_text: JSON string from OCR response

        Returns:
            OCRResult object

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

            return response

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
            self.logger.debug(f"minimal image preprocessing started mode={image.mode} size={image.size}")

            # Only ensure RGB format for LLM compatibility - no aggressive preprocessing
            # Based on user feedback: preprocessing causes more harm than good for accuracy
            if image.mode != "RGB":
                final_image = image.convert("RGB")
                self.logger.debug("image converted to RGB for llm compatibility")
            else:
                final_image = image

            self.logger.debug(f"minimal preprocessing completed mode={final_image.mode} size={final_image.size}")

            return final_image

        except (AttributeError, TypeError) as e:
            # Handle cases where we might be working with a mock object during testing
            self.logger.warning("image preprocessing failed error=%s; using original image", str(e))

            # Return original image if preprocessing fails (e.g., during testing with mocks)
            # Ensure it's in RGB format for LLM processing
            if hasattr(image, "convert") and hasattr(image, "mode"):
                return image.convert("RGB") if image.mode != "RGB" else image
            else:
                return image

    @staticmethod
    def _image_to_data_url(image: Image.Image) -> str:
        """Convert PIL image to an inline JPEG data URL for multimodal model input."""
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

    async def extract_text(self, image: Image.Image) -> OCRResult:
        """
        Extract text from a Swedish textbook page image with enhanced preprocessing.

        Args:
            image: PIL Image object to process

        Returns:
            OCRResult object containing extracted text and metadata

        Raises:
            OCRError: If text extraction fails
        """
        start_time = time.time()
        try:
            # Log original image characteristics for debugging
            self.logger.debug(f"text extraction started mode={image.mode} size={image.size}")

            # Basic validation and size adjustment
            if image.mode not in ["RGB", "RGBA", "L"]:
                self.logger.debug(f"image converting to RGB from_mode={image.mode}")
                image = image.convert("RGB")

            # Check image size (basic validation)
            width, height = image.size
            if width < 100 or height < 100:
                self.logger.error(f"image too small width={width} height={height}")
                raise ImageProcessingError("Image is too small (minimum 100x100 pixels)")

            if width > 4096 or height > 4096:
                # Resize large images to prevent API issues
                self.logger.debug(f"large image resizing from_size={image.size}")
                image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
                self.logger.debug(f"large image resized to_size={image.size}")

            # ENHANCEMENT: Apply preprocessing for better light-blue text detection
            self.logger.debug("image preprocessing started")
            preprocessed_image = self._preprocess_image_for_ocr(image)
            self.logger.debug("image preprocessing completed")

            # Build OCR prompt using PromptBuilder
            self.logger.debug("ocr prompt build started")
            ocr_prompt = self.builder.build_ocr_prompt()
            self.logger.debug("ocr prompt built length=%s", len(ocr_prompt))

            image_data_url = self._image_to_data_url(preprocessed_image)
            self.logger.info(
                "extracting text provider=%s model=%s",
                self.settings.resolve_ocr_llm_provider(),
                self.settings.resolve_ocr_llm_model(),
            )
            ocr_model = self.model.bind(max_tokens=10000, temperature=0.1)
            extracted_text = extract_message_text(
                await ocr_model.ainvoke(
                    [
                        HumanMessage(
                            content=[
                                {"type": "text", "text": ocr_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_data_url,
                                        "detail": "high",
                                    },
                                },
                            ]
                        )
                    ]
                )
            )

            # Check if we got a valid response
            if not extracted_text:
                self.logger.error("ocr returned no text")
                raise OCRError("No text returned from OCR processing")

            self.logger.debug("ocr response received length=%s", len(extracted_text))

            # Parse and analyze recognition statistics
            self.logger.debug("ocr response parsing and validation started")
            ocr_response = self._parse_and_analyze_recognition_stats(extracted_text)
            stats = ocr_response.recognition_statistics
            self.logger.debug(f"Recognition stats: {stats.successfully_transcribed}/{stats.total_elements} elements")

            # Check if extracted text is too short
            if len(ocr_response.transcribed_text) < 10:
                self.logger.error("ocr text too short length=%s", len(ocr_response.transcribed_text))
                raise OCRError("Extracted text is too short - may not be a valid textbook page")

            self.logger.debug("ocr extraction successful characters=%s", len(ocr_response.transcribed_text))

            processing_time = time.time() - start_time
            self.logger.info("ocr processing completed latency_s=%.2f", processing_time)

            return ocr_response

        except OCRError:
            self.logger.error("ocr error raised; re-raising")
            raise
        except Exception as e:
            self.logger.error("ocr unexpected error type=%s", type(e).__name__)
            self.logger.error("ocr unexpected error message=%s", str(e))
            raise OCRError(f"OCR processing failed: {type(e).__name__}: {str(e)}")
