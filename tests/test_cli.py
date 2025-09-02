"""
Tests for the CLI module.
"""

from pathlib import Path
from unittest.mock import Mock, patch

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

    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_success(self, mock_processor_class):
        """Test successful process command execution."""
        # Create a real temporary file for testing
        with self.runner.isolated_filesystem():
            # Create a dummy image file
            Path(self.test_image_path).touch()

            # Mock processor and results
            mock_processor = Mock()
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
            mock_processor_class.assert_called_once_with(provider="openai", api_key=self.api_key, model_name=None, verbose=True)
            mock_processor.process_image.assert_called_once()
            mock_processor.display_results_console.assert_called_once_with(mock_results)

    def test_process_command_missing_api_key(self):
        """Test process command without API key."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            result = self.runner.invoke(cli, ["process", self.test_image_path])

            assert result.exit_code == 1
            assert "OpenAI API key is required" in result.output  # noqa: E501

    def test_process_command_file_not_found(self):
        """Test process command with non-existent file."""
        result = self.runner.invoke(cli, ["process", "nonexistent.jpg", "--api-key", self.api_key])

        assert result.exit_code == 1
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
            mock_processor = Mock()
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
            mock_processor = Mock()
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
            mock_processor = Mock()
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
            mock_processor = Mock()
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

    @patch.dict("os.environ", {"GEMINI_API_KEY": "env-api-key"})
    @patch("runestone.cli.RunestoneProcessor")
    def test_process_command_env_api_key(self, mock_processor_class):
        """Test process command using API key from environment."""
        with self.runner.isolated_filesystem():
            Path(self.test_image_path).touch()

            # Mock processor and results
            mock_processor = Mock()
            mock_results = {
                "ocr_result": {"text": "Test text", "character_count": 9},
                "analysis": {"grammar_focus": {}, "vocabulary": []},
                "resources": [],
            }
            mock_processor.process_image.return_value = mock_results
            mock_processor_class.return_value = mock_processor

            result = self.runner.invoke(cli, ["process", self.test_image_path])

            assert result.exit_code == 0
            # Should use API key from environment
            mock_processor_class.assert_called_once_with(provider="openai", api_key="env-api-key", model_name=None, verbose=False)
