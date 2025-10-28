"""
Service layer for grammar operations.

This module contains service classes that handle business logic
for grammar-related operations.
"""

import os
import re
from typing import List

from ..core.logging_config import get_logger


class GrammarService:
    """Service for grammar-related business logic."""

    def __init__(self):
        """Initialize service."""
        self.logger = get_logger(__name__)
        self.cheatsheets_dir = "cheatsheets"

    def list_cheatsheets(self) -> List[dict]:
        """Scan cheatsheets directory, filter for .md files, return sorted list of cheatsheet info."""
        try:
            if not os.path.exists(self.cheatsheets_dir):
                self.logger.warning(f"Cheatsheets directory '{self.cheatsheets_dir}' does not exist")
                return []

            files = []
            for filename in os.listdir(self.cheatsheets_dir):
                if filename.endswith(".md"):
                    title = self._filename_to_title(filename)
                    files.append({"filename": filename, "title": title})

            # Sort by title
            files.sort(key=lambda x: x["title"])
            return files

        except Exception as e:
            self.logger.error(f"Error listing cheatsheets: {e}")
            return []

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
