"""
Tests for the OCR processing module.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from runestone.config import Settings
from runestone.core.exceptions import ImageProcessingError, OCRError
from runestone.core.ocr import OCRProcessor


class TestOCRProcessor:
    """Test cases for OCRProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key"
        self.test_image_path = Path("test_image.jpg")
        self.settings = Settings()

    def test_init_success(self):
        """Test successful initialization."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client, verbose=True)

        assert processor.client == mock_client
        assert processor.verbose is True

    @patch("PIL.Image.open")
    def test_load_and_validate_image_success(self, mock_image_open):
        """Test successful image loading and validation."""
        # Mock PIL Image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

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

        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

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

        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)

        assert "too small" in str(exc_info.value)

    @patch("PIL.Image.open")
    def test_load_image_file_not_found(self, mock_image_open):
        """Test error handling for missing image file."""
        mock_image_open.side_effect = FileNotFoundError("File not found")

        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        with pytest.raises(ImageProcessingError) as exc_info:
            processor._load_and_validate_image(self.test_image_path)

        assert "Image file not found" in str(exc_info.value)

    def test_extract_text_success(self):
        """Test successful text extraction."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini JSON response
        mock_response = Mock()
        mock_response.text = """{
            "transcribed_text": "Svenska text från läroboken",
            "recognition_statistics": {
                "total_elements": 50,
                "successfully_transcribed": 50,
                "unclear_uncertain": 0,
                "unable_to_recognize": 0
            }
        }"""

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)
        result = processor.extract_text(mock_image)

        # Verify result structure
        assert isinstance(result, dict)
        assert result["text"] == "Svenska text från läroboken"
        assert result["character_count"] == len("Svenska text från läroboken")

        # Verify LLM client was called correctly
        mock_client.extract_text_from_image.assert_called_once()
        args = mock_client.extract_text_from_image.call_args[0]
        assert len(args) == 2  # preprocessed_image and ocr_prompt
        assert "accurately transcribe all readable text" in args[1]

    def test_extract_text_error_response(self):
        """Test handling of OCR error response."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini error response
        mock_response = Mock()
        mock_response.text = """{"error": "Could not recognize text on the page."}"""

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)

        with pytest.raises(OCRError) as exc_info:
            processor.extract_text(mock_image)

        assert "Could not recognize text on the page." in str(exc_info.value)

    def test_extract_text_too_short(self):
        """Test handling of text that is too short."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock Gemini JSON response with very short text
        mock_response = Mock()
        mock_response.text = """{
            "transcribed_text": "Hi",
            "recognition_statistics": {
                "total_elements": 1,
                "successfully_transcribed": 1,
                "unclear_uncertain": 0,
                "unable_to_recognize": 0
            }
        }"""

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)

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

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)

        with pytest.raises(OCRError) as exc_info:
            processor.extract_text(mock_image)

        assert "No text returned" in str(exc_info.value)

    def test_parse_and_analyze_recognition_stats_success(self):
        """Test successful parsing and analysis of recognition statistics."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        # Test JSON response with good recognition stats
        test_json = """{
            "transcribed_text": "This is the main content of the page.",
            "recognition_statistics": {
                "total_elements": 100,
                "successfully_transcribed": 95,
                "unclear_uncertain": 3,
                "unable_to_recognize": 2
            }
        }"""

        result = processor._parse_and_analyze_recognition_stats(test_json)

        # Should return cleaned text
        expected_text = "This is the main content of the page."
        assert result == expected_text

    def test_parse_and_analyze_recognition_stats_low_percentage(self):
        """Test that OCRError is raised when recognition percentage is below 90%."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        # Test JSON response with poor recognition stats
        test_json = """{
            "transcribed_text": "This is the main content.",
            "recognition_statistics": {
                "total_elements": 100,
                "successfully_transcribed": 85,
                "unclear_uncertain": 10,
                "unable_to_recognize": 5
            }
        }"""

        with pytest.raises(OCRError) as exc_info:
            processor._parse_and_analyze_recognition_stats(test_json)

        assert "OCR recognition percentage below 90%: 85.0% (85/100)" in str(exc_info.value)
        assert "total_elements" in exc_info.value.details

    def test_parse_and_analyze_recognition_stats_no_stats(self):
        """Test handling when no recognition statistics are present."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        # Test JSON response without statistics (empty stats object)
        test_json = """{
            "transcribed_text": "This is plain text without statistics.",
            "recognition_statistics": {}
        }"""

        result = processor._parse_and_analyze_recognition_stats(test_json)

        # Should return the transcribed text
        assert result == "This is plain text without statistics."

    def test_parse_and_analyze_recognition_stats_zero_total(self):
        """Test handling when total text elements is zero."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        # Test JSON response with zero total elements
        test_json = """{
            "transcribed_text": "Some content.",
            "recognition_statistics": {
                "total_elements": 0,
                "successfully_transcribed": 0,
                "unclear_uncertain": 0,
                "unable_to_recognize": 0
            }
        }"""

        result = processor._parse_and_analyze_recognition_stats(test_json)

        # Should return transcribed text without raising error
        expected_text = "Some content."
        assert result == expected_text

    def test_parse_and_analyze_recognition_stats_boundary_percentage(self):
        """Test boundary case where percentage is exactly 90%."""
        mock_client = Mock()
        processor = OCRProcessor(settings=self.settings, client=mock_client)

        # Test JSON response with exactly 90% recognition
        test_json = """{
            "transcribed_text": "Content.",
            "recognition_statistics": {
                "total_elements": 100,
                "successfully_transcribed": 90,
                "unclear_uncertain": 5,
                "unable_to_recognize": 5
            }
        }"""

        result = processor._parse_and_analyze_recognition_stats(test_json)

        # Should succeed (not raise error) since 90% is acceptable
        expected_text = "Content."
        assert result == expected_text

    def test_extract_text_with_stats_parsing(self):
        """Test that extract_text properly parses and removes statistics."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock JSON response with stats
        mock_response = Mock()
        mock_response.text = """{
            "transcribed_text": "Extracted Swedish text content.",
            "recognition_statistics": {
                "total_elements": 100,
                "successfully_transcribed": 95,
                "unclear_uncertain": 3,
                "unable_to_recognize": 2
            }
        }"""

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)
        result = processor.extract_text(mock_image)

        # Verify result contains cleaned text
        assert result["text"] == "Extracted Swedish text content."
        assert result["character_count"] == len("Extracted Swedish text content.")

    def test_extract_text_with_low_recognition_raises_error(self):
        """Test that extract_text raises OCRError for low recognition percentage."""
        # Mock image
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)

        # Mock JSON response with poor stats
        mock_response = Mock()
        mock_response.text = """{
            "transcribed_text": "Some text.",
            "recognition_statistics": {
                "total_elements": 100,
                "successfully_transcribed": 80,
                "unclear_uncertain": 15,
                "unable_to_recognize": 5
            }
        }"""

        mock_client = Mock()
        mock_client.extract_text_from_image.return_value = mock_response.text

        processor = OCRProcessor(settings=self.settings, client=mock_client)

        with pytest.raises(OCRError) as exc_info:
            processor.extract_text(mock_image)

        assert "OCR recognition percentage below 90%: 80.0% (80/100)" in str(exc_info.value)
