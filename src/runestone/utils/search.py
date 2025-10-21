"""
Utility functions for search query parsing and wildcard handling.

This module provides functions to convert user-facing search queries with
wildcards (* and ?) into SQL LIKE patterns with proper escaping.
"""


def parse_search_query_with_wildcards(query: str) -> str:
    r"""
    Parse a search query with user-facing wildcards (* and ?) and convert to SQL LIKE pattern.

    The function correctly handles escape sequences:
    - Backslash (\) is used to escape special characters
    - \* becomes a literal asterisk
    - \? becomes a literal question mark
    - \\ becomes a literal backslash
    - Unescaped * becomes SQL LIKE wildcard %
    - Unescaped ? becomes SQL LIKE wildcard _
    - SQL special characters (%, _) in the input are escaped to treat them as literals

    Args:
        query: The search query string with user-facing wildcards

    Returns:
        A SQL LIKE pattern with proper escaping, ready to use with escape="\\"

    Examples:
        >>> parse_search_query_with_wildcards("hello*")
        'hello%'
        >>> parse_search_query_with_wildcards("hello?")
        'hello_'
        >>> parse_search_query_with_wildcards(r"hello\*")
        'hello\\*'
        >>> parse_search_query_with_wildcards("50%")
        '50\\%'
        >>> parse_search_query_with_wildcards("a_b")
        'a\\_b'
        >>> parse_search_query_with_wildcards(r"c:\\path")
        'c:\\\\path'
    """
    result = []
    i = 0
    length = len(query)

    while i < length:
        char = query[i]

        if char == "\\":
            # Handle escape sequences
            if i + 1 < length:
                next_char = query[i + 1]
                if next_char in ("*", "?", "\\"):
                    # Escaped wildcard or backslash - treat as literal
                    # Need to escape it for SQL LIKE
                    if next_char == "*":
                        result.append("\\*")
                    elif next_char == "?":
                        result.append("\\?")
                    else:  # next_char == "\\"
                        result.append("\\\\")
                    i += 2  # Skip both the backslash and the escaped character
                    continue
                else:
                    # Backslash followed by a non-special character
                    # Treat the backslash as a literal backslash
                    result.append("\\\\")
                    i += 1
                    continue
            else:
                # Backslash at the end of the string - treat as literal
                result.append("\\\\")
                i += 1
                continue
        elif char == "*":
            # Unescaped * - convert to SQL LIKE wildcard %
            result.append("%")
        elif char == "?":
            # Unescaped ? - convert to SQL LIKE wildcard _
            result.append("_")
        elif char == "%":
            # SQL special character - escape it
            result.append("\\%")
        elif char == "_":
            # SQL special character - escape it
            result.append("\\_")
        else:
            # Regular character - pass through as-is
            result.append(char)

        i += 1

    return "".join(result)
