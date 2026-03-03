"""
Tests for the CLI module.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from click.testing import CliRunner

from runestone.cli import cli
from runestone.core.exceptions import RunestoneError


class TestCLI:
    """Test cases for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.test_image_path = "test_image.jpg"
        self.api_key = "test-api-key"

    def test_cli_group_help(self):
        """Test CLI group help message."""
        result = self.runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Runestone" in result.output
        assert "Swedish textbook pages" in result.output

    def test_process_command_help(self):
        """Test process command help message."""
        result = self.runner.invoke(cli, ["process", "--help"])

        assert result.exit_code == 0
        assert "Process a Swedish textbook page" in result.output
        assert "IMAGE_PATH" in result.output

    @patch("runestone.cli.ContentAnalyzer")
    @patch("runestone.cli.OCRProcessor")
    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_success(self, mock_processor_class, mock_ocr_class, mock_analyzer_class):
        """Test successful process command execution."""
        # Create a real temporary file for testing
        with self.runner.isolated_filesystem():
            # Create a dummy image file
            Path(self.test_image_path).touch()

            # Mock processor and results
            mock_processor = AsyncMock()
            mock_results = {
                "ocr_result": {"text": "Test text", "character_count": 9},
                "analysis": {"grammar_focus": {}, "vocabulary": []},
                "resources": [],
            }
            mock_processor.process_image.return_value = mock_results
            mock_processor_class.return_value = mock_processor

            # Run command
            result = self.runner.invoke(
                cli,
                [
                    "process",
                    self.test_image_path,
                    "--api-key",
                    self.api_key,
                    "--verbose",
                ],
            )

            assert result.exit_code == 0
            # Check that processor was called with correct parameters
            call_args = mock_processor_class.call_args
            assert call_args[1]["verbose"] is True
            assert "settings" in call_args[1]
            assert "ocr_processor" in call_args[1]
            assert "content_analyzer" in call_args[1]
            mock_processor.process_image.assert_called_once()
            mock_processor.display_results_console.assert_called_once_with(mock_results)

    @patch("runestone.cli.settings")
    @patch("PIL.Image.open")
    def test_process_command_missing_api_key(self, mock_image_open, mock_settings):
        """Test process command without API key."""
        # Mock the global settings instance to return None for API keys
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = None
        mock_settings.gemini_api_key = None
        mock_settings.openrouter_api_key = None
        mock_settings.ocr_llm_provider = None
        mock_settings.verbose = False

        # Mock PIL Image to avoid image loading error
        mock_image = Mock()
        mock_image.mode = "RGB"
        mock_image.size = (800, 600)
        mock_image_open.return_value = mock_image

        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            result = self.runner.invoke(cli, ["process", self.test_image_path])

            assert result.exit_code == 1
            # Check for API key error message
            assert "api key" in result.output.lower()

    def test_process_command_file_not_found(self):
        """Test process command with non-existent file."""
        result = self.runner.invoke(cli, ["process", "nonexistent.jpg", "--api-key", self.api_key])

        assert result.exit_code == 2  # Click's Path validation returns exit code 2 for non-existent files
        assert "does not exist" in result.output

    def test_process_command_non_image_file(self):
        """Test process command with non-image file extension."""
        with self.runner.isolated_filesystem():
            # Create a text file with non-image extension
            test_file = "test.txt"
            Path(test_file).touch()

            result = self.runner.invoke(cli, ["process", test_file, "--api-key", self.api_key])

            # Should show warning but continue (exit code could be 0 or 1 depending on implementation)
            assert "may not be an image file" in result.output  # noqa: E501

    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_runestone_error(self, mock_processor_class):
        """Test process command with Runestone error."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor that raises RunestoneError
            mock_processor = AsyncMock()
            mock_processor.process_image.side_effect = RunestoneError("Test error")
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(cli, ["process", self.test_image_path, "--api-key", self.api_key])

            assert result.exit_code == 1
            assert "Test error" in result.output  # noqa: E501

    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_unexpected_error(self, mock_processor_class):
        """Test process command with unexpected error."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor that raises unexpected error
            mock_processor = AsyncMock()
            mock_processor.process_image.side_effect = ValueError("Unexpected error")
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(cli, ["process", self.test_image_path, "--api-key", self.api_key])

            assert result.exit_code == 1
            assert "Unexpected error" in result.output  # noqa: E501

    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_keyboard_interrupt(self, mock_processor_class):
        """Test process command with keyboard interrupt."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor that raises KeyboardInterrupt
            mock_processor = AsyncMock()
            mock_processor.process_image.side_effect = KeyboardInterrupt()
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(cli, ["process", self.test_image_path, "--api-key", self.api_key])

            assert result.exit_code == 1
            assert "Operation cancelled" in result.output  # noqa: E501

    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_markdown_output(self, mock_processor_class):
        """Test process command with markdown output format."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor and results
            mock_processor = AsyncMock()
            mock_results = {
                "ocr_result": {"text": "Test text", "character_count": 9},
                "analysis": {"grammar_focus": {}, "vocabulary": []},
                "resources": [],
            }
            mock_processor.process_image.return_value = mock_results
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(
                cli,
                [
                    "process",
                    self.test_image_path,
                    "--api-key",
                    self.api_key,
                    "--output-format",
                    "markdown",
                ],
            )

            assert result.exit_code == 0
            mock_processor.display_results_markdown.assert_called_once_with(mock_results)

    def test_version_option(self):
        """Test version option."""
        result = self.runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @patch("runestone.cli.settings")
    @patch("runestone.cli.create_llm_client")
    @patch("runestone.cli.ContentAnalyzer")
    @patch("runestone.cli.OCRProcessor")
    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_env_api_key(
        self, mock_processor_class, mock_ocr_class, mock_analyzer_class, mock_create_client, mock_settings
    ):
        """Test process command using API key from environment."""
        # Mock the global settings instance to use the test API key
        mock_settings.llm_provider = "openai"
        mock_settings.openai_api_key = "env-api-key"
        mock_settings.gemini_api_key = None
        mock_settings.openrouter_api_key = None
        mock_settings.ocr_llm_provider = None
        mock_settings.verbose = False

        # Mock LLM client
        mock_llm_client = Mock()
        mock_create_client.return_value = mock_llm_client

        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor and results
            mock_processor = AsyncMock()
            mock_results = {
                "ocr_result": {"text": "Test text", "character_count": 9},
                "analysis": {"grammar_focus": {}, "vocabulary": []},
                "resources": [],
            }
            mock_processor.process_image.return_value = mock_results
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(cli, ["process", self.test_image_path])

            assert result.exit_code == 0
            # Check that processor was called with correct parameters
            call_args = mock_processor_class.call_args
            # verbose can be True if VERBOSE env var is set in actual environment
            assert "settings" in call_args[1]
            assert "ocr_processor" in call_args[1]
            assert "content_analyzer" in call_args[1]

    def test_load_vocab_command_help(self):
        """Test load_vocab command help message."""
        result = self.runner.invoke(cli, ["load-vocab", "--help"])

        assert result.exit_code == 0
        assert "Load vocabulary data" in result.output
        assert "--skip-existence-check" in result.output

    @patch("runestone.cli.VocabularyService")
    def test_load_vocab_command_skip_check(self, mock_service_class):
        """Test load_vocab command with skip existence check."""
        with self.runner.isolated_filesystem():
            # Create a test CSV file
            csv_content = "word1;translation1;example1\nword2;translation2;example2\n"
            csv_path = "test_vocab.csv"
            with open(csv_path, "w") as f:
                f.write(csv_content)

            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.load_vocab_from_csv.return_value = {"original_count": 2, "added_count": 2, "skipped_count": 0}

            result = self.runner.invoke(cli, ["load-vocab", csv_path, "--skip-existence-check"])

            assert result.exit_code == 0
            mock_service.load_vocab_from_csv.assert_called_once()
            assert "Processed 2 vocabulary items" in result.output

    @patch("runestone.cli.VocabularyService")
    def test_load_vocab_command_default_check(self, mock_service_class):
        """Test load_vocab command with default existence check."""
        with self.runner.isolated_filesystem():
            # Create a test CSV file
            csv_content = "word1;translation1;example1\nword2;translation2;example2\n"
            csv_path = "test_vocab.csv"
            with open(csv_path, "w") as f:
                f.write(csv_content)

            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.load_vocab_from_csv.return_value = {"original_count": 2, "added_count": 2, "skipped_count": 0}

            result = self.runner.invoke(cli, ["load-vocab", csv_path])

            assert result.exit_code == 0
            mock_service.load_vocab_from_csv.assert_called_once()
            assert "Added 2 new vocabulary items" in result.output

    @patch("runestone.cli.GrammarIndex")
    def test_rag_search_command(self, mock_index_class):
        """Test RAG search command."""
        mock_index = Mock()
        mock_doc = Mock()
        mock_doc.metadata = {"url": "http://test.url", "annotation": "Test annotation"}
        mock_index.search.return_value = [mock_doc]
        mock_index_class.return_value = mock_index

        result = self.runner.invoke(cli, ["rag", "search", "test query"])

        assert result.exit_code == 0
        assert "Search results for: test query" in result.output
        assert "Test annotation" in result.output
        assert "http://test.url" in result.output
        mock_index.search.assert_called_once_with("test query", top_k=5)
