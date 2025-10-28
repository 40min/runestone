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

    def get_cheatsheet_content(self, filename: str) -> str:
        """Validate filename and return cheatsheet content."""
        # Validate filename to prevent path traversal attacks
        if not self._is_valid_filename(filename):
            raise ValueError(f"Invalid filename: {filename}")

        filepath = os.path.join(self.cheatsheets_dir, filename)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except FileNotFoundError:
            raise FileNotFoundError(f"Cheatsheet '{filename}' not found")
        except Exception as e:
            self.logger.error(f"Error reading cheatsheet '{filename}': {e}")
            raise

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
