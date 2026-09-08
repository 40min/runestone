"""Tests for error tracking initialization and sanitized telemetry export."""

import copy
import json
import logging
from collections.abc import Generator
from typing import Any, Literal, cast, get_args, get_origin
from unittest.mock import Mock, patch

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from runestone.config import AgentLLMSettings, Settings
from runestone.core import error_tracking
from runestone.core.error_tracking import _PROVIDERS, _sanitize_breadcrumb, _sanitize_event, setup_error_tracking

TEST_SENTINELS = (
    "SENTINEL-password",
    "SENTINEL-prompt",
    "SENTINEL-chat",
    "SENTINEL-jwt",
    "SENTINEL-email",
    "SENTINEL-telegram-id",
    "SENTINEL-cookie",
    "SENTINEL-header",
    "SENTINEL-exc-value",
    "SENTINEL-var",
    "SENTINEL-crumb",
    "SENTINEL-future",
    "SENTINEL-logentry",
)


class _InMemoryTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)


def _settings(dsn: "str | None" = "https://token@example.com/123") -> Mock:
    settings = Mock(spec=Settings)
    settings.sentry_dsn = dsn
    settings.sentry_environment = "production"
    settings.sentry_release = "runestone-api@" + "a" * 40
    return settings


@pytest.fixture
def capture_transport() -> Generator[_InMemoryTransport, None, None]:
    """Run the real SDK with the production init options and an in-memory transport."""
    transport = _InMemoryTransport()
    previous_client = sentry_sdk.get_global_scope().client
    try:
        with patch("runestone.core.error_tracking.sentry_sdk.init") as init:
            setup_error_tracking(_settings())

        options = dict(init.call_args.kwargs)
        options["transport"] = transport
        sentry_sdk.init(**options)
        yield transport
    finally:
        sentry_sdk.get_global_scope().set_client(previous_client)
        sentry_sdk.get_global_scope().clear_breadcrumbs()
        sentry_sdk.get_isolation_scope().clear_breadcrumbs()
        sentry_sdk.get_current_scope().clear_breadcrumbs()


def _capture_runtime_error() -> None:
    try:
        raise RuntimeError("trigger")
    except RuntimeError:
        sentry_sdk.capture_exception()


def _single_event(transport: _InMemoryTransport) -> dict[str, Any]:
    assert len(transport.envelopes) == 1
    event = transport.envelopes[0].get_event()
    assert event is not None
    return cast("dict[str, Any]", event)


def test_error_tracking_is_disabled_without_dsn() -> None:
    """Do not initialize reporting unless a deployment explicitly configures it."""
    settings = Mock(spec=Settings)
    settings.sentry_dsn = None

    with patch("runestone.core.error_tracking.sentry_sdk.init") as init:
        setup_error_tracking(settings)

    init.assert_not_called()


def test_error_tracking_uses_privacy_conscious_defaults() -> None:
    """Configure Better Stack without request bodies, PII, tracing, sessions, or logs."""
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
    assert options["auto_session_tracking"] is False
    assert options["enable_logs"] is False
    assert options["max_breadcrumbs"] == 20
    assert options["before_send"] is _sanitize_event
    assert options["before_breadcrumb"] is _sanitize_breadcrumb

    logging_integration = options["integrations"][0]
    assert logging_integration._handler is None
    assert logging_integration._sentry_logs_handler is None
    assert logging_integration._breadcrumb_handler is not None
    assert logging_integration._breadcrumb_handler.level == logging.WARNING


def test_serialized_event_includes_release_and_environment(capture_transport) -> None:
    """Serialize a captured event with the release metadata configured by the app."""
    sentry_sdk.capture_message("release metadata test")
    event = _single_event(capture_transport)

    assert event["release"] == "runestone-api@" + "a" * 40
    assert event["environment"] == "production"
    assert event["platform"] == "python"
    assert "logentry" not in event


def test_envelope_contains_only_event_items(capture_transport) -> None:
    """Never emit transaction, session, or log envelope items."""
    sentry_sdk.capture_message("envelope items test")

    assert len(capture_transport.envelopes) == 1
    item_types = [item.headers.get("type") for item in capture_transport.envelopes[0].items]
    assert item_types == ["event"]


def test_hostile_event_payload_is_dropped_by_projection() -> None:
    """Rebuild the event from the allowlist; denylisted and unknown data never survives."""
    event = {
        "event_id": "a" * 32,
        "platform": "python",
        "level": "error",
        "logger": "runestone.api",
        "release": "runestone-api@" + "a" * 40,
        "environment": "production",
        "user": {
            "id": "SENTINEL-telegram-id",
            "email": "SENTINEL-email",
            "ip_address": "10.0.0.1",
        },
        "extra": {"prompt": "SENTINEL-prompt", "chat": "SENTINEL-chat"},
        "tags": {"Authorization": "Bearer SENTINEL-jwt"},
        "logentry": {"message": "SENTINEL-logentry"},
        "request": {
            "url": "https://example.com/audio/ws?token=SENTINEL-jwt",
            "query_string": "token=SENTINEL-jwt",
            "headers": {"Authorization": "SENTINEL-header"},
            "cookies": "SESSIONID=SENTINEL-cookie",
            "data": {"chat": "SENTINEL-chat"},
            "method": "POST",
        },
        "contexts": {
            "runestone": {"status_code": 500},
            "other": {"secret": "SENTINEL-future"},
        },
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "SENTINEL-exc-value",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/app/module.py",
                                "function": "handler",
                                "vars": {"password": "SENTINEL-var"},
                                "context_line": "password = 'SENTINEL-var'",
                            }
                        ]
                    },
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {
                    "type": "log",
                    "level": "warning",
                    "category": "runestone.api",
                    "message": "Bearer SENTINEL-crumb",
                    "data": {"email": "SENTINEL-email"},
                }
            ]
        },
        "some_future_field": {"nested": "SENTINEL-future"},
    }
    snapshot = copy.deepcopy(event)

    projected = _sanitize_event(event, {})

    assert projected is not None
    serialized = json.dumps(projected)
    for sentinel in TEST_SENTINELS:
        assert sentinel not in serialized
    assert set(projected) == {
        "event_id",
        "platform",
        "level",
        "logger",
        "release",
        "environment",
        "exception",
        "request",
        "contexts",
    }
    assert event == snapshot
    assert projected["request"] == {"method": "POST"}
    assert projected["contexts"] == {"runestone": {"status_code": 500}}
    assert "breadcrumbs" not in projected


def test_hostile_scope_data_never_reaches_envelope(capture_transport) -> None:
    """Scope extras, tags, user data, and exception text never reach the envelope."""
    with sentry_sdk.new_scope() as scope:
        scope.set_user({"id": "SENTINEL-telegram-id", "email": "SENTINEL-email"})
        scope.set_extra("prompt", "SENTINEL-prompt")
        scope.set_tag("Authorization", "Bearer SENTINEL-jwt")
        scope.set_context("runestone", {"status_code": 502})
        try:
            raise ValueError("password=SENTINEL-password")
        except ValueError:
            sentry_sdk.capture_exception()

    event = _single_event(capture_transport)
    serialized = json.dumps(event)
    for sentinel in (
        "SENTINEL-telegram-id",
        "SENTINEL-email",
        "SENTINEL-prompt",
        "SENTINEL-jwt",
        "SENTINEL-password",
    ):
        assert sentinel not in serialized

    exception_values = event["exception"]["values"]
    assert exception_values[0]["type"] == "ValueError"
    assert "value" not in exception_values[0]
    assert event["contexts"] == {"runestone": {"status_code": 502}}


def test_allowlisted_exception_structure_survives(capture_transport) -> None:
    """Grouping stays useful: exception type, mechanism, and relative frames survive."""

    def _raise_sentinel_error() -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            sentry_sdk.capture_exception()

    _raise_sentinel_error()

    event = _single_event(capture_transport)
    exception_values = event["exception"]["values"]
    assert len(exception_values) == 1
    entry = exception_values[0]
    assert entry["type"] == "ValueError"
    assert entry["mechanism"]["handled"] is True

    frames = entry["stacktrace"]["frames"]
    assert len(frames) <= 50
    assert len(frames) > 0
    for frame in frames:
        assert not frame["filename"].startswith("/")
        assert ".." not in frame["filename"].split("/")
        assert "vars" not in frame
        assert "context_line" not in frame
    assert any(frame["function"] == "_raise_sentinel_error" for frame in frames)


def test_last_50_frames_are_kept() -> None:
    """Only the last 50 stack frames are exported."""
    frames = [
        {"filename": f"pkg/module_{index}.py", "function": f"func_{index}", "lineno": index, "in_app": True}
        for index in range(80)
    ]
    event = {
        "platform": "python",
        "exception": {"values": [{"type": "ValueError", "stacktrace": {"frames": frames}}]},
    }

    projected = _sanitize_event(event, {})

    assert projected is not None
    kept = projected["exception"]["values"][0]["stacktrace"]["frames"]
    assert len(kept) == 50
    assert kept[0]["function"] == "func_30"
    assert kept[-1]["function"] == "func_79"


def test_only_marked_runestone_warnings_become_breadcrumbs(capture_transport, caplog: pytest.LogCaptureFixture) -> None:
    """Only runestone warning/error records with a valid telemetry marker are admitted."""
    caplog.set_level(logging.DEBUG)
    runestone_logger = logging.getLogger("runestone.test")
    foreign_logger = logging.getLogger("other.logger")

    runestone_logger.warning("raw %s message", "SENTINEL-crub-arg")
    runestone_logger.info("info marked", extra={"runestone_telemetry": {"operation": "info_op"}})
    foreign_logger.warning("foreign marked", extra={"runestone_telemetry": {"operation": "foreign_op"}})
    runestone_logger.warning(
        "bad operation",
        extra={"runestone_telemetry": {"operation": "BAD OPERATION"}},
    )
    runestone_logger.warning(
        "marked message",
        extra={
            "runestone_telemetry": {
                "operation": "teacher_call",
                "route_template": "/chat/{session_id}",
                "provider": "openai",
                "model": "gpt-test-model",
                "duration_bucket": "1s_5s",
                "retry_count": 1,
                "outcome": "success",
                "status_code": 200,
            }
        },
    )
    _capture_runtime_error()

    event = _single_event(capture_transport)
    serialized = json.dumps(event)
    for sentinel in ("SENTINEL-crub-arg", "raw %s message", "marked message", "bad operation"):
        assert sentinel not in serialized

    crumbs = event["breadcrumbs"]["values"]
    assert len(crumbs) == 1
    crumb = crumbs[0]
    assert crumb["type"] == "log"
    assert crumb["level"] == "warning"
    assert crumb["category"] == "runestone.test"
    assert crumb["message"] == "teacher_call"
    assert crumb["data"] == {
        "operation": "teacher_call",
        "route_template": "/chat/{session_id}",
        "provider": "openai",
        "model": "gpt-test-model",
        "duration_bucket": "1s_5s",
        "retry_count": 1,
        "outcome": "success",
        "status_code": 200,
    }


def test_serialized_breadcrumb_bound(capture_transport, caplog: pytest.LogCaptureFixture) -> None:
    """More than 20 admitted records still serialize to at most 20 breadcrumbs."""
    caplog.set_level(logging.DEBUG)
    runestone_logger = logging.getLogger("runestone.test")
    for index in range(25):
        runestone_logger.warning(
            f"marked message {index}",
            extra={"runestone_telemetry": {"operation": f"op_{index}"}},
        )
    _capture_runtime_error()

    event = _single_event(capture_transport)
    crumbs = event["breadcrumbs"]["values"]
    assert len(crumbs) == 20


def test_failing_breadcrumb_projector_does_not_leak_original(
    capture_transport, caplog: pytest.LogCaptureFixture
) -> None:
    """Even when the internal projector raises, the unsanitized breadcrumb is dropped."""
    caplog.set_level(logging.DEBUG)
    runestone_logger = logging.getLogger("runestone.test")
    with patch(
        "runestone.core.error_tracking._project_telemetry_fields",
        side_effect=RuntimeError("projector exploded"),
    ):
        runestone_logger.warning(
            "Bearer SENTINEL-jwt",
            extra={"runestone_telemetry": {"operation": "teacher_call"}},
        )
        _capture_runtime_error()

    event = _single_event(capture_transport)
    serialized = json.dumps(event)
    assert "SENTINEL-jwt" not in serialized
    assert "teacher_call" not in serialized
    assert "breadcrumbs" not in event


def test_over_cap_event_fails_closed() -> None:
    """Over-cap payloads are dropped entirely."""
    event = {"event_id": "a" * 32, "platform": "python", "level": "error"}
    with patch.object(error_tracking, "_MAX_EVENT_BYTES", 8):
        assert _sanitize_event(event, {}) is None


def test_broken_projection_fails_closed() -> None:
    """Unexpected projection failures drop the event instead of leaking it."""
    with patch.object(error_tracking, "_project_event", side_effect=RuntimeError("boom")):
        assert _sanitize_event({"event_id": "a" * 32, "platform": "python"}, {}) is None


def test_transaction_requires_route_or_component_source() -> None:
    """Only route/component sources with valid route templates are exported."""

    def _project(transaction: str, source: str) -> dict:
        event = {
            "platform": "python",
            "transaction": transaction,
            "transaction_info": {"source": source},
        }
        projected = _sanitize_event(event, {})
        assert projected is not None
        return projected

    assert _project("/chat/{session_id}", "route")["transaction"] == "/chat/{session_id}"
    assert _project("/", "component")["transaction"] == "/"
    assert "transaction" not in _project("/chat/{session_id}", "url")
    for bad_template in (
        "/chat?token=SENTINEL-jwt",
        "/a//b",
        "/a/../b",
        "/chat#fragment",
        "/percent%20encoded",
        "chat/{id}",
        "/" + "a" * 200,
    ):
        assert "transaction" not in _project(bad_template, "route")


def test_status_code_validation() -> None:
    """Only integer 100..599 (or a three-digit string) is exported."""

    def _project(value: object) -> dict:
        event = {"platform": "python", "contexts": {"runestone": {"status_code": value}}}
        projected = _sanitize_event(event, {})
        assert projected is not None
        return projected

    assert _project(200)["contexts"]["runestone"]["status_code"] == 200
    assert _project("404")["contexts"]["runestone"]["status_code"] == 404
    for invalid in ("two hundred", True, False, 99, 600, 200.5, "1234", "abc", "12", None):
        assert "contexts" not in _project(invalid)


def test_maximum_breadcrumb_event_stays_under_size_cap() -> None:
    """A full 20-breadcrumb event of maximum-size fields stays under 128 KiB."""
    crumbs = [
        {
            "type": "log",
            "level": "warning",
            "category": "runestone." + "a" * 100,
            "message": "a" * 64,
            "timestamp": 1_700_000_000.5,
            "data": {
                "operation": "a" * 64,
                "route_template": "/" + "a" * 199,
                "provider": "openrouter",
                "model": "a" * 128,
                "duration_bucket": "gte_30s",
                "retry_count": 10,
                "outcome": "a" * 48,
                "status_code": 599,
            },
        }
        for _ in range(20)
    ]
    event = {"platform": "python", "breadcrumbs": {"values": crumbs}}

    projected = _sanitize_event(event, {})

    assert projected is not None
    assert len(projected["breadcrumbs"]["values"]) == 20
    serialized = json.dumps(projected, separators=(",", ":"))
    assert len(serialized.encode("utf-8")) < 128 * 1024


def _literal_values(annotation: Any) -> set[str]:
    """Collect string values from a (possibly nested/Optional) Literal annotation."""
    if get_origin(annotation) is Literal:
        return set(get_args(annotation))
    values: set[str] = set()
    for arg in get_args(annotation):
        values.update(_literal_values(arg))
    return values


def test_breadcrumb_provider_allowlist_covers_configured_llm_providers() -> None:
    """An LLM provider added to config must be added to the breadcrumb allowlist too.

    Breadcrumbs drop an unrecognized ``provider`` silently, so drift between the
    config Literals and ``_PROVIDERS`` would lose telemetry without any failure.
    Voice/TTS providers are a separate domain and deliberately out of scope.
    """
    non_llm_provider_fields = frozenset({"voice_transcription_provider", "tts_provider"})
    configured: set[str] = set()
    for name, field in Settings.model_fields.items():
        if not name.endswith("_provider") or name in non_llm_provider_fields:
            continue
        configured.update(_literal_values(field.annotation))
    configured.update(_literal_values(AgentLLMSettings.model_fields["provider"].annotation))

    # Sanity guard: the extraction must see all three LLM providers, otherwise a
    # refactor could make the subset assertion below pass vacuously.
    assert {"openai", "openrouter", "gemini"} <= configured
    assert configured <= _PROVIDERS
