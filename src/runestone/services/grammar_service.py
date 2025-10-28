"""
Service layer for grammar operations.

This module contains service classes that handle business logic
for grammar-related operations.
"""

import os
import re
from pathlib import Path
from typing import List
from urllib.parse import unquote

from ..core.logging_config import get_logger


class GrammarService:
    """Service for grammar-related business logic."""

    def __init__(self, cheatsheets_dir: str):
        """Initialize service."""
        self.logger = get_logger(__name__)
        self.cheatsheets_dir = cheatsheets_dir

    def list_cheatsheets(self) -> List[dict]:
        """Scan cheatsheets directory, filter for .md files, return sorted list of cheatsheet info."""
        if not os.path.exists(self.cheatsheets_dir):
            self.logger.warning(f"Cheatsheets directory '{self.cheatsheets_dir}' does not exist")
            return []

        files = []
        cheatsheets_path = Path(self.cheatsheets_dir)

        for item in cheatsheets_path.iterdir():
            # Scan one level of subdirectories
            if item.is_dir():
                category = item.name
                for sub_item in item.iterdir():
                    if self._is_suitable_cheatsheet(sub_item):
                        relative_path = sub_item.relative_to(cheatsheets_path).as_posix()
                        title = self._filename_to_title(sub_item.name)
                        files.append({"filename": relative_path, "title": title, "category": category})
            # Scan root directory
            elif self._is_suitable_cheatsheet(item):
                filename = item.name
                title = self._filename_to_title(filename)
                files.append({"filename": filename, "title": title, "category": "General"})

        # Sort by title
        files.sort(key=lambda x: x["title"])
        return files

    def _is_suitable_cheatsheet(self, file_item: Path) -> bool:
        return file_item.is_file() and file_item.name.endswith(".md")

    def get_cheatsheet_content(self, filepath: str) -> str:
        """Validate filepath and return cheatsheet content."""
        # Validate filepath (raises ValueError if invalid)
        self._validate_filepath(filepath)

        # Construct the full path
        cheatsheets_path = Path(self.cheatsheets_dir)
        file_path = cheatsheets_path / filepath

        # Resolve to absolute paths
        resolved_file = file_path.resolve()
        resolved_base = cheatsheets_path.resolve()

        # Security check: ensure file is within cheatsheets directory
        if not resolved_file.is_relative_to(resolved_base):
            raise ValueError(f"Invalid file path: {filepath}")

        # Check file exists and has .md extension
        if not resolved_file.exists():
            raise FileNotFoundError(f"Cheatsheet not found: {filepath}")

        # Read and return content
        return resolved_file.read_text(encoding="utf-8")

    def _validate_filepath(self, filepath: str) -> None:
        """
        Validate filepath to prevent path traversal and other security issues.

        Supports both simple filenames and paths with subdirectories (e.g., 'category/file.md').

        Raises:
            ValueError: If filepath is invalid or has security issues.
        """
        # Decode URL-encoded characters to catch encoded path traversal attempts
        decoded_filepath = unquote(filepath)

        # Check for security issues first (these should raise "Invalid file path")
        has_security_issue = (
            not filepath  # empty
            or ".." in filepath
            or "\\" in filepath  # path traversal
            or ".." in decoded_filepath
            or "\\" in decoded_filepath  # encoded path traversal
            or filepath.endswith("/")
            or filepath.endswith("\\")  # trailing slashes
            or decoded_filepath.endswith("/")
            or decoded_filepath.endswith("\\")  # encoded trailing slashes
            or re.search(r'[<>:"|?*]', filepath)  # dangerous characters
        )

        if has_security_issue:
            raise ValueError(f"Invalid file path: {filepath}")

        # Must end with .md extension for valid cheatsheet files
        if not filepath.endswith(".md"):
            raise ValueError(f"Invalid file extension: {filepath}. Only .md files are allowed.")

    def _filename_to_title(self, filename: str) -> str:
        """Convert filename to human-readable title."""
        # Remove .md extension and replace hyphens/underscores with spaces
        title = filename.replace(".md", "").replace("-", " ").replace("_", " ")

        # Capitalize each word
        return " ".join(word.capitalize() for word in title.split())
