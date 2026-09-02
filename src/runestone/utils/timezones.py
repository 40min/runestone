"""Validation helpers for persisted IANA timezone preferences."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone_name(value: str) -> str:
    """Return a trimmed supported timezone name or raise ``ValueError``."""
    normalized = value.strip()
    if normalized != "UTC" and "/" not in normalized:
        raise ValueError("Timezone must be a valid IANA timezone")

    try:
        ZoneInfo(normalized)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Timezone must be a valid IANA timezone") from exc
    return normalized


def effective_timezone_name(value: object) -> str:
    """Return a safe persisted timezone, falling back to UTC for legacy data."""
    if not isinstance(value, str):
        return "UTC"
    try:
        return validate_timezone_name(value)
    except ValueError:
        return "UTC"
