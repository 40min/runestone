"""
Tests for grammar service functionality.

This module contains tests for the grammar service.
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from runestone.services.grammar_service import GrammarService


class TestGrammarService:
    """Test cases for GrammarService."""

    @pytest.fixture
    def service(self):
        """Create a GrammarService instance."""
        return GrammarService("cheatsheets")

    @pytest.fixture
    def temp_cheatsheets_dir(self):
        """Create a temporary directory with test cheatsheet files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test markdown files
            files = {
                "adjectiv-komparation.md": "# Adjectiv Komparation\n\nContent about adjective comparison.",
                "objectspronomen.md": "# Objectspronomen\n\nContent about object pronouns.",
                "presens-perfect.md": "# Presens Perfect\n\nContent about present perfect tense.",
                "pronunciation.md": "# Pronunciation\n\nContent about Swedish pronunciation.",
                "swedish_adjectives_cheatsheet.md": (
                    "# Swedish Adjectives Cheatsheet\n\nContent about Swedish adjectives."
                ),
            }

            for filename, content in files.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # Create a non-md file to ensure it's filtered out
            non_md_file = os.path.join(temp_dir, "not_a_cheatsheet.txt")
            with open(non_md_file, "w", encoding="utf-8") as f:
                f.write("This should be ignored")

            yield temp_dir

    @pytest.fixture
    def temp_cheatsheets_with_categories(self):
        """Create a temporary directory with categorized cheatsheet files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create root level files (General category)
            root_files = {
                "pronunciation.md": "# Pronunciation\n\nContent about pronunciation.",
                "swedish_adjectives.md": "# Swedish Adjectives\n\nContent about adjectives.",
            }

            for filename, content in root_files.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # Create subdirectories with categorized files
            verbs_dir = os.path.join(temp_dir, "verbs")
            os.makedirs(verbs_dir, exist_ok=True)
            verbs_files = {
                "hjalpverb.md": "# Hjalpverb\n\nContent about auxiliary verbs.",
                "verb-forms.md": "# Verb Forms\n\nContent about verb forms.",
            }

            for filename, content in verbs_files.items():
                filepath = os.path.join(verbs_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # Create adjectives subdirectory
            adj_dir = os.path.join(temp_dir, "adjectives")
            os.makedirs(adj_dir, exist_ok=True)
            adj_files = {
                "adjectiv-komparation.md": "# Adjectiv Komparation\n\nContent about adjective comparison.",
            }

            for filename, content in adj_files.items():
                filepath = os.path.join(adj_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            yield temp_dir

    def test_list_cheatsheets_success(self, service, temp_cheatsheets_dir):
        """Test listing cheatsheets successfully."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            result = service.list_cheatsheets()

        # Should return 5 cheatsheets (excluding the .txt file)
        assert len(result) == 5

        # Check that all are dictionaries with filename and title
        for item in result:
            assert "filename" in item
            assert "title" in item
            assert item["filename"].endswith(".md")
            assert isinstance(item["title"], str)

        # Check specific titles
        titles = [item["title"] for item in result]
        assert "Adjectiv Komparation" in titles
        assert "Objectspronomen" in titles
        assert "Presens Perfect" in titles
        assert "Pronunciation" in titles
        assert "Swedish Adjectives Cheatsheet" in titles

        # Check sorting (should be alphabetical by title)
        assert result == sorted(result, key=lambda x: x["title"])

    def test_list_cheatsheets_empty_directory(self, service):
        """Test listing cheatsheets in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service, "cheatsheets_dir", temp_dir):
                result = service.list_cheatsheets()

        assert result == []

    def test_list_cheatsheets_no_md_files(self, service):
        """Test listing cheatsheets when directory has no .md files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create non-md files
            with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
                f.write("text")
            with open(os.path.join(temp_dir, "file2.json"), "w") as f:
                f.write("{}")

            with patch.object(service, "cheatsheets_dir", temp_dir):
                result = service.list_cheatsheets()

        assert result == []

    def test_list_cheatsheets_directory_not_exists(self, service):
        """Test listing cheatsheets when directory doesn't exist."""
        with patch.object(service, "cheatsheets_dir", "/nonexistent/directory"):
            result = service.list_cheatsheets()

        assert result == []

    def test_get_cheatsheet_content_success(self, service, temp_cheatsheets_dir):
        """Test getting cheatsheet content successfully."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            content = service.get_cheatsheet_content("adjectiv-komparation.md")

        assert content == "# Adjectiv Komparation\n\nContent about adjective comparison."

    def test_get_cheatsheet_content_nested_path_success(self, service, temp_cheatsheets_dir):
        """Test getting cheatsheet content with nested paths."""
        # Create a subdirectory with a file
        verbs_dir = os.path.join(temp_cheatsheets_dir, "verbs")
        os.makedirs(verbs_dir, exist_ok=True)
        nested_file = os.path.join(verbs_dir, "hjalpverb.md")
        with open(nested_file, "w", encoding="utf-8") as f:
            f.write("# Hjalpverb\n\nContent about auxiliary verbs.")

        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            content = service.get_cheatsheet_content("verbs/hjalpverb.md")

        assert content == "# Hjalpverb\n\nContent about auxiliary verbs."

    def test_get_cheatsheet_content_file_not_found(self, service, temp_cheatsheets_dir):
        """Test getting content of non-existent file."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            with pytest.raises(ValueError, match="File not found or invalid: nonexistent.md"):
                service.get_cheatsheet_content("nonexistent.md")

    def test_get_cheatsheet_content_invalid_filename_path_traversal(self, service, temp_cheatsheets_dir):
        """Test that path traversal attacks are prevented."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            # Test various path traversal attempts
            invalid_filenames = [
                "../../../etc/passwd.md",
                "file.md/../other.md",
                "file.md\\..\\other.md",
                "file.md/",
                "file.md\\",
                "file.md..",
                # URL-encoded path traversal sequences
                "file.md%2F..%2Fother.md",  # file.md/../other.md
                "file.md%5C..%5Cother.md",  # file.md\..\other.md (backslash encoded)
                "file.md%2E%2E%2Fother.md",  # file.md../other.md (double dot encoded)
                "file.md%2F%2E%2E%2Fother.md",  # file.md/.. /other.md
                "%2E%2E%2Fetc%2Fpasswd.md",  # ../../etc/passwd.md
            ]

            for filename in invalid_filenames:
                with pytest.raises(ValueError, match="Invalid file path"):
                    service.get_cheatsheet_content(filename)

    def test_get_cheatsheet_content_invalid_filename_no_md(self, service, temp_cheatsheets_dir):
        """Test that non-.md files are rejected."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            with pytest.raises(ValueError, match="File not found or invalid: file.txt"):
                service.get_cheatsheet_content("file.txt")

    def test_get_cheatsheet_content_invalid_filepath_dangerous_chars(self, service, temp_cheatsheets_dir):
        """Test that filepaths with dangerous characters are rejected."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            dangerous_filepaths = [
                "file<>.md",
                "file>.md",
                "file<.md",
                "file:.md",
                'file".md',
                "file|.md",
                "file?.md",
                "file*.md",
            ]

            for filepath in dangerous_filepaths:
                with pytest.raises(ValueError, match="Invalid file path"):
                    service.get_cheatsheet_content(filepath)

    def test_filename_to_title_conversion(self, service):
        """Test filename to title conversion."""
        test_cases = [
            ("adjectiv-komparation.md", "Adjectiv Komparation"),
            ("objectspronomen.md", "Objectspronomen"),
            ("presens-perfect.md", "Presens Perfect"),
            ("swedish_adjectives_cheatsheet.md", "Swedish Adjectives Cheatsheet"),
            ("simple.md", "Simple"),
            ("multiple-words-here.md", "Multiple Words Here"),
            ("under_score_example.md", "Under Score Example"),
        ]

        for filename, expected_title in test_cases:
            assert service._filename_to_title(filename) == expected_title

    def test_is_valid_filename(self, service):
        """Test filename validation."""
        valid_filenames = [
            "file.md",
            "adjectiv-komparation.md",
            "file_name.md",
            "file-name.md",
            "file123.md",
        ]

        for filename in valid_filenames:
            assert service._is_valid_filename(filename) is True

        invalid_filenames = [
            "",  # Empty
            "file.txt",  # Wrong extension
            "file.md/",  # Path separator
            "file.md\\",  # Backslash
            "file.md..",  # Double dot
            "file<>.md",  # Dangerous chars
            "file>.md",
            "file<.md",
            "file:.md",
            'file".md',
            "file|.md",
            "file?.md",
            "file*.md",
        ]

        for filename in invalid_filenames:
            assert service._is_valid_filename(filename) is False

    def test_list_cheatsheets_with_categories(self, service, temp_cheatsheets_with_categories):
        """Test listing cheatsheets with category support."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_with_categories):
            result = service.list_cheatsheets()

        # Should return 5 cheatsheets total
        assert len(result) == 5

        # Check that all have category field
        for item in result:
            assert "filename" in item
            assert "title" in item
            assert "category" in item

        # Check General category items (root level)
        general_items = [item for item in result if item["category"] == "General"]
        assert len(general_items) == 2
        general_filenames = [item["filename"] for item in general_items]
        assert "pronunciation.md" in general_filenames
        assert "swedish_adjectives.md" in general_filenames

        # Check verbs category items
        verbs_items = [item for item in result if item["category"] == "verbs"]
        assert len(verbs_items) == 2
        verbs_filenames = [item["filename"] for item in verbs_items]
        assert "verbs/hjalpverb.md" in verbs_filenames
        assert "verbs/verb-forms.md" in verbs_filenames

        # Check adjectives category items
        adj_items = [item for item in result if item["category"] == "adjectives"]
        assert len(adj_items) == 1
        assert adj_items[0]["filename"] == "adjectives/adjectiv-komparation.md"

    def test_list_cheatsheets_category_field_present(self, service, temp_cheatsheets_dir):
        """Test that category field is always present in results."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_dir):
            result = service.list_cheatsheets()

        # All items should have General category (root level files)
        for item in result:
            assert item["category"] == "General"

    def test_get_cheatsheet_content_with_category_path(self, service, temp_cheatsheets_with_categories):
        """Test getting cheatsheet content from categorized subdirectory."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_with_categories):
            content = service.get_cheatsheet_content("verbs/hjalpverb.md")

        assert content == "# Hjalpverb\n\nContent about auxiliary verbs."

    def test_get_cheatsheet_content_path_traversal_with_categories(self, service, temp_cheatsheets_with_categories):
        """Test that path traversal is prevented even with category paths."""
        with patch.object(service, "cheatsheets_dir", temp_cheatsheets_with_categories):
            # Try to escape from verbs directory
            with pytest.raises(ValueError, match="Invalid file path"):
                service.get_cheatsheet_content("verbs/../../../etc/passwd.md")
