"""
OCR processing module using configurable LLM providers.

This module handles image processing and text extraction from Swedish textbook pages
using various LLM providers like OpenAI or Gemini.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from PIL import Image

from .exceptions import OCRError, ImageProcessingError
from .clients.base import BaseLLMClient
from .clients.factory import create_llm_client


class OCRProcessor:
    """Handles OCR processing using configurable LLM providers."""
    
    def __init__(
        self,
        client: Optional[BaseLLMClient] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verbose: bool = False
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
                verbose=verbose
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
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
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
            Please extract ALL text from this Swedish textbook page image. Follow these instructions:

            1. Transcribe all Swedish text exactly as it appears, maintaining original formatting
            2. Include any text in boxes, exercises, grammar rules, examples, and vocabulary lists
            3. Preserve line breaks and spacing where meaningful
            4. If text is unclear, make your best guess but note uncertainty with [unclear]
            5. Ignore purely decorative elements, images, and graphics
            6. Focus on readable text content only

            Return the extracted text in a clear, organized format. If you cannot read any meaningful Swedish text, respond with "ERROR: Could not recognise text on the page."
            """
            
            if self.verbose:
                print(f"Sending image to {self.client.provider_name} for OCR processing...")
            
            # Use the client for OCR processing
            extracted_text = self.client.extract_text_from_image(image, ocr_prompt)
            
            if self.verbose:
                print(f"Successfully extracted {len(extracted_text)} characters of text")
            
            return {
                "text": extracted_text,
                "image_path": str(image_path),
                "image_size": image.size,
                "character_count": len(extracted_text)
            }
            
        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")