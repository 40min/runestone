"""
Tests for the OCR processing module.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.exceptions import APIKeyError, ImageProcessingError, OCRError
from runestone.core.ocr import OCRProcessor


class TestOCRProcessor:
    """Test cases for OCRProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.test_image_path = Path("test_image.jpg")
        self.settings = Settings()

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_init_success(self, mock_model, mock_configure):
        """Test successful initialization."""
        processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key, verbose=True)

        mock_configure.assert_called_once_with(api_key=self.api_key)
        # GeminiClient creates two models (OCR and analysis), so expect 2 calls
        assert mock_model.call_count == 2
        assert processor.verbose is True

    @patch("google.generativeai.configure")
    def test_init_api_key_error(self, mock_configure):
        """Test initialization with invalid API key."""
        mock_configure.side_effect = Exception("Invalid API key")

        with pytest.raises(APIKeyError) as exc_info:
            OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        assert "Failed to configure Gemini API" in str(exc_info.value)

    @patch("PIL.Image.open")
    def test_load_and_validate_image_success(self, mock_image_open):
        """Test successful image loading and validation."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        result = processor._load_and_validate_image(self.test_image_path)

        assert result == mock_image
        mock_image_open.assert_called_once_with(self.test_image_path)

    @patch("PIL.Image.open")
    def test_load_image_convert_mode(self, mock_image_open):
        """Test image mode conversion."""
        # Mock PIL Image with non-RGB mode
        mock_image = Mock()
        mock_image.mode = "RGBA"
        mock_image.size = (800, 600)
        mock_converted = Mock()
        mock_converted.size = (800, 600)  # Mock converted image size
        mock_image.convert.return_value = mock_converted
        mock_image_open.return_value = mock_image

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        result = processor._load_and_validate_image(self.test_image_path)

        mock_image.convert.assert_called_once_with("RGB")
        assert result == mock_converted

    @patch("PIL.Image.open")
    def test_load_image_too_small(self, mock_image_open):
        """Test error handling for images that are too small."""
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (50, 50)  # Too small
        mock_image_open.return_value = mock_image

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)

        assert "too small" in str(exc_info.value)

    @patch("PIL.Image.open")
    def test_load_image_file_not_found(self, mock_image_open):
        """Test error handling for missing image file."""
        mock_image_open.side_effect = FileNotFoundError("File not found")

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)

        assert "Image file not found" in str(exc_info.value)

    def test_extract_text_success(self):
        """Test successful text extraction."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = "Svenska text från läroboken"

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)
            result = processor.extract_text(mock_image)

        # Verify result structure
        assert isinstance(result, dict)
        assert result["text"] == "Svenska text från läroboken"
        assert result["character_count"] == len("Svenska text från läroboken")

        # Verify Gemini was called correctly
        mock_model.generate_content.assert_called_once()
        args = mock_model.generate_content.call_args[0]
        assert len(args) == 1  # Single argument which is a list
        content_list = args[0]
        assert len(content_list) == 2  # prompt and image
        assert "accurately transcribe all readable text" in content_list[0]

    def test_extract_text_error_response(self):
        """Test handling of OCR error response."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini error response
        mock_response = Mock()
        mock_response.text = "ERROR: Could not recognise text on the page."

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(mock_image)

        assert "Could not recognise text on the page" in str(exc_info.value)

    def test_extract_text_too_short(self):
        """Test handling of text that is too short."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini response with very short text
        mock_response = Mock()
        mock_response.text = "Hi"  # Too short

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(mock_image)

        assert "too short" in str(exc_info.value)

    def test_extract_text_no_response(self):
        """Test handling of empty response."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock empty Gemini response
        mock_response = Mock()
        mock_response.text = None

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(mock_image)

        assert "No text returned" in str(exc_info.value)

    def test_parse_and_analyze_recognition_stats_success(self):
        """Test successful parsing and analysis of recognition statistics."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        # Test text with good recognition stats
        test_text = """This is the main content of the page.

---
Recognition Statistics:
- Total text elements identified: 100
- Successfully transcribed: 95
- Unclear/uncertain: 3
- Unable to recognize: 2
---
"""

        result = processor._parse_and_analyze_recognition_stats(test_text)

        # Should return cleaned text without stats
        expected_text = "This is the main content of the page."
        assert result == expected_text

    def test_parse_and_analyze_recognition_stats_low_percentage(self):
        """Test that OCRError is raised when recognition percentage is below 90%."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        # Test text with poor recognition stats
        test_text = """This is the main content.

---
Recognition Statistics:
- Total text elements identified: 100
- Successfully transcribed: 85
- Unclear/uncertain: 10
- Unable to recognize: 5
---
"""

        with pytest.raises(OCRError) as exc_info:
            processor._parse_and_analyze_recognition_stats(test_text)

        assert "OCR recognition percentage below 90%: 85.0% (85/100)" in str(exc_info.value)
        assert "Total text elements identified: 100" in exc_info.value.details

    def test_parse_and_analyze_recognition_stats_no_stats(self):
        """Test handling when no recognition statistics are present."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        # Test text without stats
        test_text = "This is plain text without statistics."

        result = processor._parse_and_analyze_recognition_stats(test_text)

        # Should return the text as-is
        assert result == test_text

    def test_parse_and_analyze_recognition_stats_zero_total(self):
        """Test handling when total text elements is zero."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        # Test text with zero total elements
        test_text = """Some content.

---
Recognition Statistics:
- Total text elements identified: 0
- Successfully transcribed: 0
- Unclear/uncertain: 0
- Unable to recognize: 0
---
"""

        result = processor._parse_and_analyze_recognition_stats(test_text)

        # Should return cleaned text without raising error
        expected_text = "Some content."
        assert result == expected_text

    def test_parse_and_analyze_recognition_stats_boundary_percentage(self):
        """Test boundary case where percentage is exactly 90%."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel"),
        ):
            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

        # Test text with exactly 90% recognition
        test_text = """Content.

---
Recognition Statistics:
- Total text elements identified: 100
- Successfully transcribed: 90
- Unclear/uncertain: 5
- Unable to recognize: 5
---
"""

        result = processor._parse_and_analyze_recognition_stats(test_text)

        # Should succeed (not raise error) since 90% is acceptable
        expected_text = "Content."
        assert result == expected_text

    def test_extract_text_with_stats_parsing(self):
        """Test that extract_text properly parses and removes statistics."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock response with stats
        mock_response = Mock()
        mock_response.text = """Extracted Swedish text content.

---
Recognition Statistics:
- Total text elements identified: 100
- Successfully transcribed: 95
- Unclear/uncertain: 3
- Unable to recognize: 2
---
"""

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)
            result = processor.extract_text(mock_image)

        # Verify result contains cleaned text without stats
        assert result["text"] == "Extracted Swedish text content."
        assert "Recognition Statistics" not in result["text"]
        assert result["character_count"] == len("Extracted Swedish text content.")

    def test_extract_text_with_low_recognition_raises_error(self):
        """Test that extract_text raises OCRError for low recognition percentage."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock response with poor stats
        mock_response = Mock()
        mock_response.text = """Some text.

---
Recognition Statistics:
- Total text elements identified: 100
- Successfully transcribed: 80
- Unclear/uncertain: 15
- Unable to recognize: 5
---
"""

        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.GenerativeModel") as mock_model_class,
        ):
            mock_model = Mock()
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model

            processor = OCRProcessor(settings=self.settings, provider="gemini", api_key=self.api_key)

            with pytest.raises(OCRError) as exc_info:
                processor.extract_text(mock_image)

        assert "OCR recognition percentage below 90%: 80.0% (80/100)" in str(exc_info.value)