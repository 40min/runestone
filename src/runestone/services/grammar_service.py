"""
Service layer for grammar operations.

This module contains service classes that handle business logic
for grammar-related operations.
"""

import os
import re
from pathlib import Path
from typing import List

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
        if not resolved_file.exists() or resolved_file.suffix != ".md":
            raise ValueError(f"File not found or invalid: {filepath}")

        # Read and return content
        return resolved_file.read_text(encoding="utf-8")

    def _is_valid_filename(self, filename: str) -> bool:
        """Validate filename to prevent path traversal attacks."""
        if not filename or not filename.endswith(".md"):
            return False

        # Check for path traversal characters
        if "/" in filename or "\\" in filename or ".." in filename:
            return False

        # Check for other potentially dangerous characters using regex whitelist
        if re.search(r"[^a-zA-Z0-9._-]", filename):
            return False

        return True

    def _filename_to_title(self, filename: str) -> str:
        """Convert filename to human-readable title."""
        # Remove .md extension and replace hyphens/underscores with spaces
        title = filename.replace(".md", "").replace("-", " ").replace("_", " ")

        # Capitalize each word
        return " ".join(word.capitalize() for word in title.split())
