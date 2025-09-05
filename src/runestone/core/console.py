"""
Console configuration module for Runestone.

This module provides centralized setup and access to the Rich Console instance
used throughout the application for consistent output formatting.
"""

from rich.console import Console

# Global console instance
_console: Console = None


def setup_console() -> Console:
    """
    Setup and return the global Console instance.

    Returns:
        Configured Console instance
    """
    global _console
    if _console is None:
        _console = Console()
    return _console


def get_console() -> Console:
    """
    Get the global Console instance.

    Returns:
        The configured Console instance

    Raises:
        RuntimeError: If console has not been set up yet
    """
    if _console is None:
        raise RuntimeError("Console has not been set up. Call setup_console() first.")
    return _console
