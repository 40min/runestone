"""
Tests for the OCR processing module.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from runestone.core.ocr import OCRProcessor
from runestone.core.exceptions import OCRError, APIKeyError, ImageProcessingError


class TestOCRProcessor:
    """Test cases for OCRProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.test_image_path = Path("test_image.jpg")
    
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_init_success(self, mock_model, mock_configure):
        """Test successful initialization."""
        processor = OCRProcessor(self.api_key, verbose=True)
        
        mock_configure.assert_called_once_with(api_key=self.api_key)
        mock_model.assert_called_once_with('gemini-2.0-flash-exp')
        assert processor.verbose is True
    
    @patch('google.generativeai.configure')
    def test_init_api_key_error(self, mock_configure):
        """Test initialization with invalid API key."""
        mock_configure.side_effect = Exception("Invalid API key")
        
        with pytest.raises(APIKeyError) as exc_info:
            OCRProcessor(self.api_key)
        
        assert "Failed to configure Gemini API" in str(exc_info.value)
    
    @patch('PIL.Image.open')
    def test_load_and_validate_image_success(self, mock_image_open):
        """Test successful image loading and validation."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            processor = OCRProcessor(self.api_key)
        
        result = processor._load_and_validate_image(self.test_image_path)
        
        assert result == mock_image
        mock_image_open.assert_called_once_with(self.test_image_path)
    
    @patch('PIL.Image.open')
    def test_load_image_convert_mode(self, mock_image_open):
        """Test image mode conversion."""
        # Mock PIL Image with non-RGB mode
        mock_image = Mock()
        mock_image.mode = 'RGBA'
        mock_image.size = (800, 600)
        mock_converted = Mock()
        mock_image.convert.return_value = mock_converted
        mock_image_open.return_value = mock_image
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            processor = OCRProcessor(self.api_key)
        
        result = processor._load_and_validate_image(self.test_image_path)
        
        mock_image.convert.assert_called_once_with('RGB')
        assert result == mock_converted
    
    @patch('PIL.Image.open')
    def test_load_image_too_small(self, mock_image_open):
        """Test error handling for images that are too small."""
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (50, 50)  # Too small
        mock_image_open.return_value = mock_image
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            processor = OCRProcessor(self.api_key)
        
        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)
        
        assert "too small" in str(exc_info.value)
    
    @patch('PIL.Image.open')
    def test_load_image_file_not_found(self, mock_image_open):
        """Test error handling for missing image file."""
        mock_image_open.side_effect = FileNotFoundError("File not found")
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            processor = OCRProcessor(self.api_key)
        
        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)
        
        assert "Image file not found" in str(exc_info.value)
    
    @patch('PIL.Image.open')
    def test_extract_text_success(self, mock_image_open):
        """Test successful text extraction."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image
        
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = "Svenska text från läroboken"
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            processor = OCRProcessor(self.api_key)
            result = processor.extract_text(self.test_image_path)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert result["text"] == "Svenska text från läroboken"
        assert result["image_path"] == str(self.test_image_path)
        assert result["image_size"] == (800, 600)
        assert result["character_count"] == len("Svenska text från läroboken")
        
        # Verify Gemini was called correctly
        mock_model.generate_content.assert_called_once()
        args = mock_model.generate_content.call_args[0]
        assert len(args) == 2  # prompt and image
        assert "extract ALL text" in args[0]
    
    @patch('PIL.Image.open')
    def test_extract_text_error_response(self, mock_image_open):
        """Test handling of OCR error response."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image
        
        # Mock Gemini error response
        mock_response = Mock()
        mock_response.text = "ERROR: Could not recognise text on the page."
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            processor = OCRProcessor(self.api_key)
            
            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(self.test_image_path)
        
        assert "Could not recognise text on the page" in str(exc_info.value)
    
    @patch('PIL.Image.open')
    def test_extract_text_too_short(self, mock_image_open):
        """Test handling of text that is too short."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image
        
        # Mock Gemini response with very short text
        mock_response = Mock()
        mock_response.text = "Hi"  # Too short
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            processor = OCRProcessor(self.api_key)
            
            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(self.test_image_path)
        
        assert "too short" in str(exc_info.value)
    
    @patch('PIL.Image.open')
    def test_extract_text_no_response(self, mock_image_open):
        """Test handling of empty response."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image
        
        # Mock empty Gemini response
        mock_response = Mock()
        mock_response.text = None
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            processor = OCRProcessor(self.api_key)
            
            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(self.test_image_path)
        
        assert "No text returned" in str(exc_info.value)