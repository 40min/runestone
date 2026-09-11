"""Tests for error tracking initialization and sanitized telemetry export."""

import asyncio
import copy
import json
import logging
import re
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, Literal, cast, get_args, get_origin
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from runestone.agents.manager import AgentsManager
from runestone.auth.dependencies import get_current_user
from runestone.config import AgentLLMSettings, ReasoningLevel, Settings
from runestone.core import error_tracking
from runestone.core.error_tracking import (
    _PROVIDERS,
    RequestCorrelationMiddleware,
    _sanitize_breadcrumb,
    _sanitize_event,
    setup_error_tracking,
)
from runestone.core.logging_config import RunestoneLogFilter, get_current_request_id
from runestone.dependencies import get_chat_service


@pytest.fixture
def mock_settings():
    """Local copy of the manager settings fixture; agents tests define their own."""
    settings = Mock(spec=Settings)
    settings.teacher_provider = "openrouter"
    settings.teacher_model = "test-model"
    settings.teacher_backup_provider = "gemini"
    settings.teacher_backup_model = None
    settings.coordinator_model = "test-coordinator-model"
    settings.coordinator_provider = "openrouter"
    settings.word_keeper_provider = "openrouter"
    settings.word_keeper_model = "test-model"
    settings.news_agent_provider = "openrouter"
    settings.news_agent_model = "test-model"
    settings.memory_keeper_provider = "openrouter"
    settings.memory_keeper_model = "test-model"
    settings.memory_maintainer_provider = "openrouter"
    settings.memory_maintainer_model = "test-memory-maintainer-model"
    settings.memory_mastered_cleanup_days = 7
    settings.memory_maintenance_timeout_seconds = 240.0
    settings.agent_persona = "default"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    settings.allowed_origins = "http://localhost:5173"
    settings.telegram_offset_file_path = "state/offset.txt"
    settings.get_agent_llm_settings.side_effect = lambda agent_name: {
        "teacher": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=1.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=10.0,
            max_retries=3,
        ),
        "coordinator": AgentLLMSettings(
            provider="openrouter",
            model="test-coordinator-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=3.0,
            max_retries=3,
        ),
        "word_keeper": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=15.0,
            max_retries=3,
        ),
        "news_agent": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=10.0,
            max_retries=3,
        ),
        "memory_keeper": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=15.0,
            max_retries=3,
        ),
        "learning_memory_keeper": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=15.0,
            max_retries=3,
        ),
        "personal_memory_keeper": AgentLLMSettings(
            provider="openrouter",
            model="test-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=8.0,
            max_retries=2,
        ),
        "memory_maintainer": AgentLLMSettings(
            provider="openrouter",
            model="test-memory-maintainer-model",
            temperature=0.0,
            reasoning_level=ReasoningLevel.NONE,
            timeout_seconds=30.0,
            max_retries=3,
        ),
    }[agent_name]
    return settings


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


def test_request_id_validation_and_union_merge() -> None:
    """The runestone context is a validated union of request_id and status_code."""

    def _project(runestone: object) -> dict:
        event = {"platform": "python", "contexts": {"runestone": runestone}}
        projected = _sanitize_event(event, {})
        assert projected is not None
        return projected

    valid_id = "0123456789abcdef0123456789abcdef"
    both = _project({"status_code": 500, "request_id": valid_id})
    assert both["contexts"]["runestone"] == {"status_code": 500, "request_id": valid_id}

    only_id = _project({"request_id": valid_id})
    assert only_id["contexts"]["runestone"] == {"request_id": valid_id}

    only_status = _project({"status_code": 502})
    assert only_status["contexts"]["runestone"] == {"status_code": 502}

    for invalid in (
        valid_id.upper(),
        "0" * 31,
        "0" * 33,
        "g" * 32,
        12345678901234567890123456789012,
        True,
        None,
        {"hex": valid_id},
    ):
        projected = _project({"status_code": 500, "request_id": invalid})
        assert projected["contexts"]["runestone"] == {"status_code": 500}

    assert "contexts" not in _project({"request_id": "not-a-uuid-hex-value"})


async def test_isolation_scope_request_id_reaches_captured_event(capture_transport) -> None:
    """A request ID bound to the isolation scope survives event projection."""
    request_id = "b" * 32
    sentry_sdk.get_isolation_scope().set_context("runestone", {"request_id": request_id})
    try:
        _capture_runtime_error()
    finally:
        sentry_sdk.get_isolation_scope().remove_context("runestone")

    event = _single_event(capture_transport)
    assert event["contexts"]["runestone"]["request_id"] == request_id


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request"}


async def _noop_send(message: dict[str, Any]) -> None:
    return None


async def _run_request(middleware: RequestCorrelationMiddleware, scope: dict[str, Any]) -> None:
    """Drive one request the way Sentry's ASGI integration does in production."""
    with sentry_sdk.isolation_scope():
        await middleware(scope, _noop_receive, _noop_send)


async def test_middleware_binds_request_id_to_events_in_request_scope(capture_transport) -> None:
    """HTTP scopes get a fresh 32-hex request ID visible to captured events."""

    async def inner_app(scope, receive, send) -> None:
        sentry_sdk.capture_message("inside request")

    middleware = RequestCorrelationMiddleware(inner_app)
    await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})

    event = _single_event(capture_transport)
    request_id = event["contexts"]["runestone"]["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


async def test_middleware_binds_same_request_id_to_local_logs(capture_transport, caplog) -> None:
    """Logs emitted inside the request carry the same ID as the Sentry context."""
    caplog.set_level(logging.INFO)
    logged_ids: list[str | None] = []

    async def inner_app(scope, receive, send) -> None:
        logging.getLogger("runestone.test").info("inside request")
        logged_ids.append(get_current_request_id())
        sentry_sdk.capture_message("inside request")

    middleware = RequestCorrelationMiddleware(inner_app)
    # The root handler's filter runs at emission in production; caplog's own
    # handler bypasses it, so install the production filter on the emitting
    # logger to observe the record field at emission time.
    test_logger = logging.getLogger("runestone.test")
    emission_filter = RunestoneLogFilter()
    test_logger.addFilter(emission_filter)
    try:
        await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})
    finally:
        test_logger.removeFilter(emission_filter)

    exported_id = _single_event(capture_transport)["contexts"]["runestone"]["request_id"]
    assert logged_ids == [exported_id]
    assert caplog.records[0].request_id == exported_id


async def test_middleware_resets_request_id_after_request(caplog) -> None:
    """The ContextVar is restored after the request; later logs carry no ID."""
    caplog.set_level(logging.INFO)

    async def inner_app(scope, receive, send) -> None:
        pass

    middleware = RequestCorrelationMiddleware(inner_app)
    await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})

    assert get_current_request_id() is None
    test_logger = logging.getLogger("runestone.test")
    emission_filter = RunestoneLogFilter()
    test_logger.addFilter(emission_filter)
    try:
        test_logger.info("after request")
    finally:
        test_logger.removeFilter(emission_filter)
    assert caplog.records[-1].request_id is None


async def test_concurrent_requests_bind_distinct_ids_to_local_logs(capture_transport) -> None:
    """Overlapping requests log under their own ID, never another request's."""
    barrier = asyncio.Barrier(5)
    logged_ids: list[str | None] = []

    async def inner_app(scope, receive, send) -> None:
        await barrier.wait()
        logged_ids.append(get_current_request_id())

    middleware = RequestCorrelationMiddleware(inner_app)
    scopes = [{"type": "http", "method": "GET", "path": "/x", "index": index} for index in range(5)]
    await asyncio.gather(*(_run_request(middleware, scope) for scope in scopes))

    assert len(logged_ids) == 5
    assert len(set(logged_ids)) == 5
    for request_id in logged_ids:
        assert re.fullmatch(r"[0-9a-f]{32}", request_id or "")


async def test_escaping_exception_resets_context_var_but_keeps_sentry_id(capture_transport) -> None:
    """The ContextVar is reset even when the app raises; Sentry keeps the ID."""

    async def inner_app(scope, receive, send) -> None:
        raise RuntimeError("escape")

    middleware = RequestCorrelationMiddleware(inner_app)
    with sentry_sdk.isolation_scope():
        with pytest.raises(RuntimeError, match="escape"):
            await middleware({"type": "http", "method": "GET", "path": "/x"}, _noop_receive, _noop_send)

    assert get_current_request_id() is None


async def test_concurrent_requests_receive_distinct_request_ids(capture_transport) -> None:
    """Overlapping HTTP requests never share or leak a request ID."""
    barrier = asyncio.Barrier(5)
    event_ids: list[str] = []

    async def inner_app(scope, receive, send) -> None:
        await barrier.wait()
        event_ids.append(cast("str", sentry_sdk.capture_message("concurrent")))

    middleware = RequestCorrelationMiddleware(inner_app)
    scopes = [{"type": "http", "method": "GET", "path": "/x", "index": index} for index in range(5)]
    await asyncio.gather(*(_run_request(middleware, scope) for scope in scopes))

    assert len(event_ids) == 5
    request_ids = []
    for envelope in capture_transport.envelopes:
        event = envelope.get_event()
        assert event is not None
        request_ids.append(event["contexts"]["runestone"]["request_id"])
    assert len(set(request_ids)) == 5
    for request_id in request_ids:
        assert re.fullmatch(r"[0-9a-f]{32}", request_id)


async def test_completed_request_does_not_leak_request_id(capture_transport) -> None:
    """A request ID never survives into events captured after the request."""

    async def inner_app(scope, receive, send) -> None:
        sentry_sdk.capture_message("inside request")

    middleware = RequestCorrelationMiddleware(inner_app)
    await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})
    sentry_sdk.capture_message("after request")

    assert len(capture_transport.envelopes) == 2
    later_event = capture_transport.envelopes[1].get_event()
    assert later_event is not None
    assert "request_id" not in later_event.get("contexts", {}).get("runestone", {})


async def test_escaping_exception_is_captured_with_request_id(capture_transport) -> None:
    """An exception escaping the middleware is captured with the ID still bound.

    Sentry's outer ASGI integration captures the escaping exception after this
    middleware has returned; the context must therefore not be removed early.
    """

    async def inner_app(scope, receive, send) -> None:
        raise RuntimeError("escape")

    middleware = RequestCorrelationMiddleware(inner_app)
    with sentry_sdk.isolation_scope():
        try:
            await middleware({"type": "http", "method": "GET", "path": "/x"}, _noop_receive, _noop_send)
        except RuntimeError:
            sentry_sdk.capture_exception()

    event = _single_event(capture_transport)
    assert re.fullmatch(r"[0-9a-f]{32}", event["contexts"]["runestone"]["request_id"])


async def test_outer_sentry_asgi_wrapper_captures_escaping_exception_with_request_id(
    capture_transport,
) -> None:
    """The real SentryAsgiMiddleware captures the exception and the ID survives.

    This drives the production middleware order: Sentry's ASGI integration
    outermost, request correlation inside it, automatic exception capture (no
    manual capture call in the test).
    """
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

    async def inner_app(scope, receive, send) -> None:
        raise RuntimeError("escape")

    asgi_app = SentryAsgiMiddleware(RequestCorrelationMiddleware(inner_app))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
    }

    with pytest.raises(RuntimeError, match="escape"):
        await asgi_app(scope, _noop_receive, _noop_send)

    event = _single_event(capture_transport)
    assert re.fullmatch(r"[0-9a-f]{32}", event["contexts"]["runestone"]["request_id"])
    exception_values = event["exception"]["values"]
    assert exception_values[0]["type"] == "RuntimeError"


async def test_middleware_merges_into_existing_runestone_context(capture_transport) -> None:
    """A pre-existing runestone context survives alongside the new request ID."""
    sentry_sdk.get_isolation_scope().set_context("runestone", {"status_code": 500})
    try:

        async def inner_app(scope, receive, send) -> None:
            sentry_sdk.capture_message("inside request")

        middleware = RequestCorrelationMiddleware(inner_app)
        await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})
    finally:
        sentry_sdk.get_isolation_scope().remove_context("runestone")

    event = _single_event(capture_transport)
    runestone = event["contexts"]["runestone"]
    assert runestone["status_code"] == 500
    assert re.fullmatch(r"[0-9a-f]{32}", runestone["request_id"])


async def test_websocket_scope_passes_through_without_request_id(capture_transport) -> None:
    """WebSocket scopes are not correlated and do not mutate the ambient scope."""

    async def inner_app(scope, receive, send) -> None:
        sentry_sdk.capture_message("websocket")

    middleware = RequestCorrelationMiddleware(inner_app)
    await _run_request(middleware, {"type": "websocket", "path": "/ws"})

    event = _single_event(capture_transport)
    assert "request_id" not in event.get("contexts", {}).get("runestone", {})


async def test_middleware_is_inert_when_sdk_is_disabled(capture_transport, monkeypatch) -> None:
    """Without an initialized SDK the middleware never mutates ambient state."""
    monkeypatch.setattr(sentry_sdk, "is_initialized", lambda: False)

    async def inner_app(scope, receive, send) -> None:
        sentry_sdk.capture_message("disabled mode")

    middleware = RequestCorrelationMiddleware(inner_app)
    await _run_request(middleware, {"type": "http", "method": "GET", "path": "/x"})

    event = _single_event(capture_transport)
    assert "request_id" not in event.get("contexts", {}).get("runestone", {})


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


class _FailingChatServiceStub:
    """Invoke the real manager producer path, then fail the request."""

    def __init__(self, manager: AgentsManager) -> None:
        self._manager = manager

    async def process_message(self, user_id: int, message: str, tts_expected: bool = False, speed: float = 1.0):
        return await self._manager.generate_teacher_response(
            message=message,
            history=[],
            user=SimpleNamespace(id=user_id),  # type: ignore[arg-type]
            pre_results=[],
            active_learning_focus_memory="",
        )


async def test_chat_message_failure_exports_named_breadcrumb_and_request_id(
    capture_transport,
    mock_settings,
) -> None:
    """The production capture path exports the marked breadcrumb, route, and request ID only."""
    from runestone.api import main as api_main

    manager = AgentsManager(mock_settings)
    manager.teacher = AsyncMock()
    manager.teacher.generate_response = AsyncMock(side_effect=ValueError("SENTINEL-exc-value"))

    app = api_main.create_application()
    app.dependency_overrides[get_chat_service] = lambda: _FailingChatServiceStub(manager)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=987654321)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/chat/message?tracking=SENTINEL-query",
                json={"message": "SENTINEL-prompt"},
                headers={"Authorization": "Bearer SENTINEL-header"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500

    assert len(capture_transport.envelopes) == 1
    envelope = capture_transport.envelopes[0]
    serialized = envelope.serialize()
    for sentinel in (
        "SENTINEL-exc-value",
        "SENTINEL-prompt",
        "SENTINEL-header",
        "SENTINEL-query",
        "987654321",
        "chat response generation failed",
        "teacher response generation failed",
    ):
        assert sentinel.encode() not in serialized

    event = envelope.get_event()
    assert event is not None
    assert event["transaction"] == "/api/chat/message"
    assert event["request"] == {"method": "POST"}
    request_id = event["contexts"]["runestone"]["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)

    crumbs = event["breadcrumbs"]["values"]
    assert [crumb["message"] for crumb in crumbs] == ["teacher_response"]
    assert crumbs[0]["data"] == {
        "operation": "teacher_response",
        "outcome": "failed",
        "provider": "openrouter",
        "model": "test-model",
    }
