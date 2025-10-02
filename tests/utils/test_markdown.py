"""
Tests for markdown utility functions.
"""

from runestone.utils.markdown import escape_markdown


class TestEscapeMarkdown:
    """Test cases for the escape_markdown function."""

    def test_escape_special_characters(self):
        """Test that special Markdown characters are properly escaped."""
        test_cases = [
            ("*", "\\*"),
            ("_", "\\_"),
            ("[", "\\["),
            ("]", "\\]"),
            ("(", "\\("),
            (")", "\\)"),
            ("~", "\\~"),
            ("`", "\\`"),
            (">", "\\>"),
            ("#", "\\#"),
            ("+", "\\+"),
            ("-", "\\-"),
            ("=", "\\="),
            ("|", "\\|"),
            ("{", "\\{"),
            ("}", "\\}"),
            (".", "\\."),
            ("!", "\\!"),
        ]

        for input_char, expected in test_cases:
            result = escape_markdown(input_char)
            assert result == expected, f"Failed to escape '{input_char}': got '{result}', expected '{expected}'"

    def test_escape_multiple_characters(self):
        """Test escaping multiple special characters in a string."""
        input_text = "*bold* _italic_ [link](url) ~strikethrough~ `code` > quote # header + - = | { } . !"
        expected = (
            r"\*bold\* \_italic\_ \[link\]\(url\) \~strikethrough\~ \`code\` \> quote \# header \+ "
            r"\- \= \| \{ \} \. \!"
        )

        result = escape_markdown(input_text)
        assert result == expected

    def test_no_double_escaping(self):
        """Test that already escaped characters are not double-escaped."""
        test_cases = [
            (r"\*", r"\*"),  # Already escaped asterisk
            (r"\_", r"\_"),  # Already escaped underscore
            (r"\\[", r"\\["),  # Already escaped bracket
            (r"\\]", r"\\]"),  # Already escaped bracket
            (r"\(", r"\("),  # Already escaped parenthesis
            (r"\)", r"\)"),  # Already escaped parenthesis
        ]

        for input_text, expected in test_cases:
            result = escape_markdown(input_text)
            assert result == expected, f"Double-escaped '{input_text}': got '{result}', expected '{expected}'"

    def test_mixed_escaped_and_unescaped(self):
        """Test strings with both escaped and unescaped special characters."""
        input_text = r"Already \*escaped\* but _not_ this [or] this"
        expected = r"Already \*escaped\* but \_not\_ this \[or\] this"

        result = escape_markdown(input_text)
        assert result == expected

    def test_no_special_characters(self):
        """Test that strings without special characters are unchanged."""
        input_text = "Hello world 123"
        result = escape_markdown(input_text)
        assert result == input_text

    def test_empty_string(self):
        """Test that empty strings are handled correctly."""
        result = escape_markdown("")
        assert result == ""

    def test_only_backslashes(self):
        """Test strings with only backslashes."""
        input_text = r"\\\\\\"
        result = escape_markdown(input_text)
        assert result == input_text  # Backslashes should not be escaped

    def test_complex_text(self):
        """Test a complex text with various special characters."""
        input_text = (
            "Check this: *bold*, _italic_, `code`, > quote, # header, + plus, - minus, = equals, | pipe, "
            "{ brace }, . dot, ! exclamation"
        )
        expected = (
            r"Check this: \*bold\*, \_italic\_, \`code\`, \> quote, \# header, \+ plus, \- minus, \= equals, "
            r"\| pipe, \{ brace \}, \. dot, \! exclamation"
        )
        result = escape_markdown(input_text)
        assert result == expected

    def test_telegram_markdown_v2_compatibility(self):
        """Test compatibility with Telegram MarkdownV2 escaping requirements."""
        # Test the characters that Telegram MarkdownV2 requires escaping
        telegram_special_chars = "_*[]()~`>#+-=|{}.!"

        for char in telegram_special_chars:
            result = escape_markdown(char)
            assert result == f"\\{char}", f"Failed to escape Telegram special char '{char}': got '{result}'"
