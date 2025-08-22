"""
Gemini LLM client implementation.

This module provides a Gemini-specific implementation of the BaseLLMClient
interface, handling OCR and content analysis using Google's Gemini API.
"""

import google.generativeai as genai
from PIL import Image
from typing import Dict, Any

from .base import BaseLLMClient
from ..exceptions import APIKeyError, OCRError, LLMError


class GeminiClient(BaseLLMClient):
    """Gemini implementation of the LLM client interface."""

    def __init__(self, api_key: str, verbose: bool = False):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Google Gemini API key
            verbose: Enable verbose logging
        """
        super().__init__(api_key, verbose)
        self._configure_client()

    def _configure_client(self) -> None:
        """Configure Gemini API client."""
        try:
            genai.configure(api_key=self.api_key)
            
            # OCR model (without tools)
            self.ocr_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Analysis model with search tool
            self.search_tool = genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name="google_search",
                        description="Search Google for Swedish language learning resources",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "query": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Search query for Swedish learning resources"
                                )
                            },
                            required=["query"]
                        )
                    )
                ]
            )
            
            self.analysis_model = genai.GenerativeModel(
                'gemini-2.0-flash-exp',
                tools=[self.search_tool]
            )
            
        except Exception as e:
            raise APIKeyError(f"Failed to configure Gemini API: {str(e)}")

    def extract_text_from_image(self, image: Image.Image, prompt: str) -> str:
        """
        Extract text from an image using Gemini Vision API.
        
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
                print("Sending image to Gemini for OCR processing...")
            
            response = self.ocr_model.generate_content([prompt, image])
            
            if not response.text:
                raise OCRError("No text returned from Gemini API")
            
            extracted_text = response.text.strip()
            
            # Check for error response
            if "ERROR: Could not recognise text on the page" in extracted_text:
                raise OCRError("Could not recognise text on the page.")
            
            if len(extracted_text) < 10:
                raise OCRError("Extracted text is too short - may not be a valid textbook page")
            
            if self.verbose:
                print(f"Successfully extracted {len(extracted_text)} characters of text")
            
            return extracted_text
            
        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR processing failed: {str(e)}")

    def analyze_content(self, prompt: str) -> str:
        """
        Analyze content using Gemini.
        
        Args:
            prompt: Analysis prompt
            
        Returns:
            Analysis result as string
            
        Raises:
            LLMError: If content analysis fails
        """
        try:
            if self.verbose:
                print("Analyzing content with Gemini...")
            
            response = self.analysis_model.generate_content(prompt)
            
            if not response.text:
                raise LLMError("No analysis returned from Gemini")
            
            return response.text.strip()
            
        except Exception as e:
            raise LLMError(f"Content analysis failed: {str(e)}")

    def search_resources(self, prompt: str) -> str:
        """
        Search for learning resources using Gemini.
        
        Args:
            prompt: Search prompt
            
        Returns:
            Search results as string
            
        Raises:
            LLMError: If resource search fails
        """
        try:
            if self.verbose:
                print("Searching for resources with Gemini...")
            
            response = self.analysis_model.generate_content(prompt)
            
            if not response.text:
                raise LLMError("No search results returned from Gemini")
            
            return response.text.strip()
            
        except Exception as e:
            raise LLMError(f"Resource search failed: {str(e)}")

    @property
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        return "gemini"

    @property
    def model_name(self) -> str:
        """Return the name of the model being used."""
        return "gemini-2.0-flash-exp"