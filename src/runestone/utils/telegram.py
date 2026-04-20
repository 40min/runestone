"""Helpers for Telegram integration."""


def normalize_telegram_username(username: str | None) -> str | None:
    """Return the canonical Telegram username used for account linking."""
    if username is None:
        return None

    normalized = username.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    normalized = normalized.strip().lower()
    return normalized or None
