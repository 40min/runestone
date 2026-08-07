"""Configure privacy-conscious application error tracking."""

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from runestone.config import Settings


def _scrub_sensitive_event_data(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Remove query values that may contain JWTs or user-entered text."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("query_string", None)
        url = request.get("url")
        if isinstance(url, str):
            request["url"] = url.partition("?")[0]

    return event


def setup_error_tracking(settings: Settings) -> None:
    """Initialize Sentry-compatible error reporting when a DSN is configured."""
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=settings.sentry_release,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=_scrub_sensitive_event_data,
        integrations=[LoggingIntegration(level=None, event_level=None, sentry_logs_level=None)],
    )
