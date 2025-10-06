"""
Utilities for Markdown text processing.
"""

import re


def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters for Telegram's MarkdownV2 format.

    This function escapes all special characters, even if they are already escaped.
    This is a simple approach that ensures all special characters are escaped.

    Args:
        text: The text to escape

    Returns:
        The text with special characters escaped
    """
    # Use alternation to avoid issues with [ and ] in character class
    escape_pattern = r"(\_|\*|\[|\]|\(|\)|\~|\`|\>|\#|\+|\-|\=|\||\{|\}|\.|\!)"

    return re.sub(escape_pattern, r"\\\1", text)
