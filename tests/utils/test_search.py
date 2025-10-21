"""
Tests for search utility functions.
"""

from runestone.utils.search import parse_search_query_with_wildcards


class TestParseSearchQueryWithWildcards:
    """Tests for parse_search_query_with_wildcards function."""

    def test_no_wildcards_plain_text(self):
        """Test that plain text without wildcards is returned as-is."""
        assert parse_search_query_with_wildcards("hello") == "hello"
        assert parse_search_query_with_wildcards("hello world") == "hello world"

    def test_asterisk_wildcard_to_percent(self):
        """Test that unescaped * is converted to SQL % wildcard."""
        assert parse_search_query_with_wildcards("hello*") == "hello%"
        assert parse_search_query_with_wildcards("*world") == "%world"
        assert parse_search_query_with_wildcards("hello*world") == "hello%world"
        assert parse_search_query_with_wildcards("**") == "%%"

    def test_question_wildcard_to_underscore(self):
        """Test that unescaped ? is converted to SQL _ wildcard."""
        assert parse_search_query_with_wildcards("hello?") == "hello_"
        assert parse_search_query_with_wildcards("?world") == "_world"
        assert parse_search_query_with_wildcards("hello?world") == "hello_world"
        assert parse_search_query_with_wildcards("??") == "__"

    def test_escaped_asterisk(self):
        """Test that \\* is treated as a literal asterisk."""
        assert parse_search_query_with_wildcards(r"hello\*") == r"hello\*"
        assert parse_search_query_with_wildcards(r"\*world") == r"\*world"
        assert parse_search_query_with_wildcards(r"hello\*world") == r"hello\*world"

    def test_escaped_question_mark(self):
        """Test that \\? is treated as a literal question mark."""
        assert parse_search_query_with_wildcards(r"hello\?") == r"hello\?"
        assert parse_search_query_with_wildcards(r"\?world") == r"\?world"
        assert parse_search_query_with_wildcards(r"hello\?world") == r"hello\?world"

    def test_escaped_backslash(self):
        """Test that \\\\ is treated as a literal backslash."""
        assert parse_search_query_with_wildcards(r"hello\\") == r"hello\\"
        assert parse_search_query_with_wildcards(r"\\world") == r"\\world"
        assert parse_search_query_with_wildcards(r"hello\\world") == r"hello\\world"

    def test_sql_percent_escape(self):
        """Test that SQL % character is escaped."""
        assert parse_search_query_with_wildcards("50%") == r"50\%"
        assert parse_search_query_with_wildcards("100% match") == r"100\% match"

    def test_sql_underscore_escape(self):
        """Test that SQL _ character is escaped."""
        assert parse_search_query_with_wildcards("hello_world") == r"hello\_world"
        assert parse_search_query_with_wildcards("test_case") == r"test\_case"

    def test_mixed_wildcards_and_escapes(self):
        """Test combinations of wildcards and escape sequences."""
        # Mix of wildcards and escaped wildcards
        assert parse_search_query_with_wildcards(r"*test\*") == r"%test\*"
        assert parse_search_query_with_wildcards(r"?test\?") == r"_test\?"

        # Mix of wildcards and SQL special chars
        assert parse_search_query_with_wildcards("*50%") == r"%50\%"
        assert parse_search_query_with_wildcards("?test_") == r"_test\_"

        # Mix of everything
        assert parse_search_query_with_wildcards(r"*\*?_50%") == r"%\*_\_50\%"

    def test_backslash_at_end(self):
        """Test that a backslash at the end is treated as a literal."""
        assert parse_search_query_with_wildcards("hello\\") == r"hello\\"

    def test_backslash_before_regular_char(self):
        """Test that backslash before a regular character is treated as literal."""
        assert parse_search_query_with_wildcards(r"hello\world") == r"hello\\world"
        assert parse_search_query_with_wildcards(r"\test") == r"\\test"

    def test_windows_path_example(self):
        """Test realistic example: Windows path with backslashes."""
        assert parse_search_query_with_wildcards(r"c:\windows\system32") == r"c:\\windows\\system32"

    def test_multiple_escapes_in_sequence(self):
        """Test multiple escape sequences in a row."""
        assert parse_search_query_with_wildcards(r"\*\?\*") == r"\*\?\*"
        assert parse_search_query_with_wildcards(r"\\\\") == r"\\\\"

    def test_empty_string(self):
        """Test that empty string is handled correctly."""
        assert parse_search_query_with_wildcards("") == ""

    def test_only_wildcards(self):
        """Test string containing only wildcards."""
        assert parse_search_query_with_wildcards("*") == "%"
        assert parse_search_query_with_wildcards("?") == "_"
        assert parse_search_query_with_wildcards("*?*") == "%_%"

    def test_only_escape_sequences(self):
        """Test string containing only escape sequences."""
        assert parse_search_query_with_wildcards(r"\*") == r"\*"
        assert parse_search_query_with_wildcards(r"\?") == r"\?"
        assert parse_search_query_with_wildcards(r"\\") == r"\\"

    def test_complex_real_world_patterns(self):
        """Test complex, real-world search patterns."""
        # Searching for a file pattern with escaped wildcards
        assert parse_search_query_with_wildcards(r"test\*.py") == r"test\*.py"

        # Searching with mix of wildcards and literals
        assert parse_search_query_with_wildcards(r"log_*_2024\*.txt") == r"log\_%\_2024\*.txt"

        # Searching for SQL-like pattern
        assert parse_search_query_with_wildcards("SELECT * FROM %users%") == r"SELECT % FROM \%users\%"

    def test_unicode_characters(self):
        """Test that unicode characters are handled correctly."""
        assert parse_search_query_with_wildcards("hello*世界") == "hello%世界"
        assert parse_search_query_with_wildcards("café*") == "café%"
        assert parse_search_query_with_wildcards("привет?мир") == "привет_мир"

    def test_bug_case_escaped_asterisk_should_be_literal(self):
        """
        Test the specific bug mentioned in the task.

        When a user wants to search for a literal * and inputs \\*,
        the result should be a literal asterisk (\\*), not a wildcard.
        """
        # This is the key test case that demonstrates the bug fix
        result = parse_search_query_with_wildcards(r"\*")
        assert result == r"\*", "Escaped asterisk should be treated as literal, not as wildcard"

        # Similarly for question mark
        result = parse_search_query_with_wildcards(r"\?")
        assert result == r"\?", "Escaped question mark should be treated as literal, not as wildcard"
