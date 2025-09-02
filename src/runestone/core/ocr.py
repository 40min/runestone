"""
OCR processing module using configurable LLM providers.

This module handles image processing and text extraction from Swedish textbook pages
using various LLM providers like OpenAI or Gemini.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from .clients.base import BaseLLMClient
from .clients.factory import create_llm_client
from .exceptions import ImageProcessingError, OCRError


class OCRProcessor:
    """Handles OCR processing using configurable LLM providers."""

    def __init__(
        self,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the OCR processor.

        Args:
            client: Pre-configured LLM client (if provided, other params are ignored)
            provider: LLM provider name ("openai" or "gemini")
            api_key: API key for the provider
            model_name: Model name to use
            verbose: Enable verbose logging
        """
        self.verbose = verbose

        if client is not None:
            self.client = client
        else:
            self.client = create_llm_client(
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                verbose=verbose,
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
                    print(f"Resized large image to {image.size}")

            return image

        except FileNotFoundError:
            raise ImageProcessingError(f"Image file not found: {image_path}")
        except Exception as e:
            raise ImageProcessingError(f"Failed to load image: {str(e)}")

    def extract_text(self, image_path: Path) -> Dict[str, Any]:
        """
        Extract text from a Swedish textbook page image.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing extracted text and metadata

        Raises:
            OCRError: If text extraction fails
        """
        try:
            # Load and validate image
            image = self._load_and_validate_image(image_path)

            # Prepare the prompt for OCR
            ocr_prompt = """
You are an expert OCR transcription assistant. Your task is to accurately transcribe all readable text from the provided image.

## Core Instructions:
1. **Exact Transcription**: Copy text exactly as it appears, preserving:
   - Original formatting and layout
   - All punctuation marks and special characters (å, ä, ö, é, ñ, etc.)
   - Capitalization patterns
   - Number formatting and mathematical notation

2. **Content Inclusion**: Transcribe ALL visible text including:
   - Main body text and headings
   - Text within boxes, frames, or highlighted areas
   - Exercise questions and instructions
   - Notes, captions, and annotations
   - Word lists and vocabulary
   - Page numbers and headers/footers
   - Table content and labels

3. **Formatting Preservation**:
   - Maintain paragraph breaks and line spacing
   - Preserve indentation and bullet points
   - Keep table structure using simple formatting
   - Use --- or === for visual separators when present

4. **Special Handling**:
   - Underscores (_) in exercises represent blank spaces for student answers - transcribe as is
   - For unclear text, use [unclear: best_guess] or [unclear] if no guess possible
   - Mark different sections clearly if the layout suggests distinct areas

5. **Quality Control**:
   - Double-check numbers, dates, and proper names
   - Verify special characters are correctly represented
   - Ensure no text is accidentally omitted

## Output Format:
Provide the transcribed text followed by recognition statistics.

If no readable text exists, respond with:
ERROR: Could not recognize text on the page.

End your transcription with:
```
---
Recognition Statistics: 
- Total text elements identified: N
- Successfully transcribed: X
- Unclear/uncertain: Y
- Unable to recognize: Z
---
```

## Important Notes:
- Ignore purely decorative elements, images, and non-text graphics
- Focus on text content only, not visual layout descriptions
- If text appears in multiple columns, transcribe left-to-right, top-to-bottom
- Maintain the original language of the text (don't translate)
"""

            # Use the client for OCR processing
            extracted_text = self.client.extract_text_from_image(image, ocr_prompt)

            if self.verbose:
                print(f"Successfully extracted {len(extracted_text)} characters of text")

            return {
                "text": extracted_text,
                "image_path": str(image_path),
                "image_size": image.size,
                "character_count": len(extracted_text),
            }

        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")
