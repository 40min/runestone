"""
Utilities for Markdown text processing.
"""

import re


def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters that are not already escaped.

    This function escapes Markdown special characters for Telegram's MarkdownV2 format,
    but only escapes characters that are not already preceded by a backslash to avoid
    double-escaping.

    Args:
        text: The text to escape

    Returns:
        The text with special characters escaped
    """
    escape_chars = ["*", "_", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

    for char in escape_chars:
        # Only escape characters that are not already preceded by a backslash
        # Use negative lookbehind (?<!\\) to check if the character is not already escaped
        pattern = f"(?<!\\\\){re.escape(char)}"
        text = re.sub(pattern, f"\\{char}", text)

    return text
