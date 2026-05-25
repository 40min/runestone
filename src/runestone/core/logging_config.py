"""
Logging configuration module for Runestone.

This module provides centralized logging setup and configuration
for consistent logging across the application.
"""

import logging
import os
import re
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

_LEADING_TAG_RE = re.compile(r"^\[[^\]]+\]\s*")


class RunestoneLogFilter(logging.Filter):
    """Attach derived display fields used by the log formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.producer = _derive_producer(record.name)
        if isinstance(record.msg, str):
            record.msg = _LEADING_TAG_RE.sub("", record.msg)
        return True


def _derive_producer(logger_name: str) -> str:
    """Build a compact, human-readable producer label from logger name."""
    parts = logger_name.split(".")
    if len(parts) >= 3 and parts[0] == "runestone":
        return ".".join(parts[-2:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return logger_name


def _resolve_color_setting() -> bool | None:
    """Resolve whether ANSI colors should be enabled for log output.

    Returns:
        True: force colors on
        False: force colors off
        None: auto-detect from output environment
    """
    setting = os.getenv("RUNESTONE_LOG_COLOR", "auto").strip().lower()
    if setting in {"1", "true", "yes", "on"}:
        return True
    if setting in {"0", "false", "no", "off"}:
        return False
    return None


def setup_logging(level: str = "INFO", format_string: Optional[str] = None, verbose: bool = False) -> None:
    """
    Set up centralized logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        verbose: If True, set log level to DEBUG for detailed logging
    """
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(producer)-22s | %(message)s"

    # Use DEBUG level if verbose mode is enabled
    if verbose:
        level = "DEBUG"

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper()))

    log_filter = RunestoneLogFilter()
    date_format = "%Y-%m-%d %H:%M:%S"
    show_color = _resolve_color_setting()

    if show_color is True:
        force_terminal = True if show_color else None
        handler = RichHandler(
            console=Console(file=sys.stdout, force_terminal=force_terminal),
            rich_tracebacks=True,
            show_time=False,
            show_level=False,
            show_path=False,
            markup=False,
            log_time_format=date_format,
        )
        handler.setFormatter(logging.Formatter(format_string, datefmt=date_format))
    elif show_color is None and sys.stdout.isatty():
        handler = RichHandler(
            console=Console(file=sys.stdout),
            rich_tracebacks=True,
            show_time=False,
            show_level=False,
            show_path=False,
            markup=False,
            log_time_format=date_format,
        )
        handler.setFormatter(logging.Formatter(format_string, datefmt=date_format))
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(format_string, datefmt=date_format))

    handler.addFilter(log_filter)
    root_logger.addHandler(handler)

    # Set specific loggers if needed
    # Suppress noisy loggers from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google.generativeai").setLevel(logging.WARNING)
    logging.getLogger("google_genai._api_client").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
