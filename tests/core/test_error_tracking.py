"""Tests for error tracking initialization."""

from unittest.mock import Mock, patch

from runestone.config import Settings
from runestone.core.error_tracking import _scrub_sensitive_event_data, setup_error_tracking


def test_error_tracking_is_disabled_without_dsn() -> None:
    """Do not initialize reporting unless a deployment explicitly configures it."""
    settings = Mock(spec=Settings)
    settings.sentry_dsn = None

    with patch("runestone.core.error_tracking.sentry_sdk.init") as init:
        setup_error_tracking(settings)

    init.assert_not_called()


def test_error_tracking_uses_privacy_conscious_defaults() -> None:
    """Configure Better Stack without request bodies, default PII, or tracing."""
    settings = Mock(spec=Settings)
    settings.sentry_dsn = "https://token@example.com/123"
    settings.sentry_environment = "production"
    settings.sentry_release = "runestone-api@abc123"

    with patch("runestone.core.error_tracking.sentry_sdk.init") as init:
        setup_error_tracking(settings)

    init.assert_called_once()
    options = init.call_args.kwargs
    assert options["dsn"] == "https://token@example.com/123"
    assert options["environment"] == "production"
    assert options["release"] == "runestone-api@abc123"
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    assert options["traces_sample_rate"] == 0.0
    assert options["before_send"] is _scrub_sensitive_event_data

    logging_integration = options["integrations"][0]
    assert logging_integration._breadcrumb_handler is None
    assert logging_integration._handler is None
    assert logging_integration._sentry_logs_handler is None


def test_sensitive_query_data_is_removed_from_events() -> None:
    """Never export JWT query parameters or user-entered query content."""
    event = {
        "request": {
            "url": "https://example.com/audio/ws?token=secret-jwt",
            "query_string": "token=secret-jwt",
        }
    }

    scrubbed_event = _scrub_sensitive_event_data(event, {})

    assert scrubbed_event["request"] == {"url": "https://example.com/audio/ws"}
    assert "secret-jwt" not in str(scrubbed_event)
