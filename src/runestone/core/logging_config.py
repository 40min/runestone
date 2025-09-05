"""
Logging configuration module for Runestone.

This module provides centralized logging setup and configuration
for consistent logging across the application.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    Set up centralized logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        stream=sys.stdout,
    )

    # Set specific loggers if needed
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)