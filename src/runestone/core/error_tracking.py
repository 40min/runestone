"""Configure privacy-conscious application error tracking.

Exported events are rebuilt from an explicit allowlist instead of redacted in
place: anything not listed is dropped, so a new SDK field cannot become
exported by upgrading the dependency. Breadcrumbs are admitted only from
code-owned ``runestone_telemetry`` markers on runestone warning/error log
records. Both callbacks fail closed without logging, because a log emission
would recurse back into the SDK.
"""

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from runestone.config import Settings

if TYPE_CHECKING:
    from sentry_sdk._types import BreadcrumbProcessor, EventProcessor

_MAX_EVENT_BYTES = 128 * 1024
_MAX_FRAMES = 50
_MAX_EXCEPTIONS = 3
_MAX_BREADCRUMBS = 20

_EVENT_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
_MECHANISM_TYPE_RE = re.compile(r"[a-z][a-z0-9_.-]{0,31}")
_FUNCTION_RE = re.compile(r"[A-Za-z0-9_.<>-]{1,200}")
_RELEASE_RE = re.compile(r"[A-Za-z0-9._:/@-]{1,128}")
_ENVIRONMENT_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
_METHOD_RE = re.compile(r"[A-Z]{3,16}")
_ROUTE_TEMPLATE_RE = re.compile(r"/[A-Za-z0-9_{}./:-]{0,199}")
_OPERATION_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_OUTCOME_RE = re.compile(r"[a-z][a-z0-9_]{0,47}")
_MODEL_RE = re.compile(r"[A-Za-z0-9._:/-]{1,128}")

_LEVELS = frozenset({"debug", "info", "warning", "error", "critical", "fatal"})
_BREADCRUMB_LEVELS = frozenset({"warning", "error", "critical"})
_PROVIDERS = frozenset({"openai", "openrouter", "gemini"})
_DURATION_BUCKETS = frozenset({"lt_100ms", "100ms_1s", "1s_5s", "5s_30s", "gte_30s"})
_RECORD_LEVEL_TO_BREADCRUMB = {
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


def _is_runestone_logger(name: Any) -> bool:
    """Accept only the application's own logger namespace, capped at 128 chars."""
    return (
        isinstance(name, str)
        and len(name) <= 128
        and (name == "runestone" or name.startswith("runestone."))
        and bool(_IDENTIFIER_RE.fullmatch(name))
    )


def _validate_route_template(value: Any) -> "str | None":
    """Accept route templates such as ``/chat/{session_id}``; ``/`` is the only root."""
    if not isinstance(value, str) or not _ROUTE_TEMPLATE_RE.fullmatch(value):
        return None
    if value == "/":
        return value
    segments = value.split("/")[1:]
    if any(segment in ("", "..") for segment in segments):
        return None
    return value


def _validate_status_code(value: Any) -> "int | None":
    """Accept integers 100..599 and three-digit strings; reject every other coercion."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and len(value) == 3 and value.isdigit():
        value = int(value)
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    return None


def _validate_number(value: Any) -> "float | int | None":
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _normalize_timestamp(value: Any) -> "float | int | None":
    """Return a JSON-safe epoch timestamp, or ``None`` when unparseable."""
    if isinstance(value, datetime):
        try:
            return value.timestamp()
        except (OverflowError, OSError, ValueError):
            return None
    return _validate_number(value)


def _validate_frame_filename(value: Any) -> "str | None":
    """Accept only relative paths without empty or ``..`` segments."""
    if not isinstance(value, str) or not value or value.startswith("/"):
        return None
    if any(segment in ("", "..") for segment in value.split("/")):
        return None
    return value


def _project_frame(frame: Any) -> "dict[str, Any] | None":
    if not isinstance(frame, dict):
        return None
    projected: dict[str, Any] = {}

    filename = _validate_frame_filename(frame.get("filename"))
    if filename is not None:
        projected["filename"] = filename

    module = frame.get("module")
    if isinstance(module, str) and _IDENTIFIER_RE.fullmatch(module):
        projected["module"] = module

    function = frame.get("function")
    if isinstance(function, str) and _FUNCTION_RE.fullmatch(function):
        projected["function"] = function

    lineno = frame.get("lineno")
    if isinstance(lineno, int) and not isinstance(lineno, bool) and 1 <= lineno <= 10_000_000:
        projected["lineno"] = lineno

    if isinstance(frame.get("in_app"), bool):
        projected["in_app"] = frame["in_app"]

    return projected or None


def _project_exception_values(value: Any) -> "list[dict[str, Any]] | None":
    if not isinstance(value, list):
        return None

    projected: list[dict[str, Any]] = []
    for exception in value[:_MAX_EXCEPTIONS]:
        if not isinstance(exception, dict):
            continue
        # An exception entry without a usable type cannot be grouped; drop the entry.
        exc_type = exception.get("type")
        if not isinstance(exc_type, str) or not _IDENTIFIER_RE.fullmatch(exc_type):
            continue

        item: dict[str, Any] = {"type": exc_type}

        module = exception.get("module")
        if isinstance(module, str) and _IDENTIFIER_RE.fullmatch(module):
            item["module"] = module

        mechanism = exception.get("mechanism")
        if isinstance(mechanism, dict):
            projected_mechanism: dict[str, Any] = {}
            mechanism_type = mechanism.get("type")
            if isinstance(mechanism_type, str) and _MECHANISM_TYPE_RE.fullmatch(mechanism_type):
                projected_mechanism["type"] = mechanism_type
            if isinstance(mechanism.get("handled"), bool):
                projected_mechanism["handled"] = mechanism["handled"]
            if projected_mechanism:
                item["mechanism"] = projected_mechanism

        stacktrace = exception.get("stacktrace")
        if isinstance(stacktrace, dict) and isinstance(stacktrace.get("frames"), list):
            frames = [
                projected_frame
                for frame in stacktrace["frames"][-_MAX_FRAMES:]
                if (projected_frame := _project_frame(frame)) is not None
            ]
            if frames:
                item["stacktrace"] = {"frames": frames}

        projected.append(item)

    return projected or None


def _project_telemetry_fields(data: Any) -> "dict[str, Any] | None":
    """Validate a ``runestone_telemetry`` mapping, keeping only allowed fields.

    Returns ``None`` unless the mandatory ``operation`` key is valid; optional
    fields are dropped individually when they fail their checks.
    """
    if not isinstance(data, dict):
        return None

    operation = data.get("operation")
    if not isinstance(operation, str) or not _OPERATION_RE.fullmatch(operation):
        return None

    projected: dict[str, Any] = {"operation": operation}

    route_template = _validate_route_template(data.get("route_template"))
    if route_template is not None:
        projected["route_template"] = route_template

    provider = data.get("provider")
    if isinstance(provider, str) and provider in _PROVIDERS:
        projected["provider"] = provider

    model = data.get("model")
    if isinstance(model, str) and _MODEL_RE.fullmatch(model):
        projected["model"] = model

    duration_bucket = data.get("duration_bucket")
    if isinstance(duration_bucket, str) and duration_bucket in _DURATION_BUCKETS:
        projected["duration_bucket"] = duration_bucket

    retry_count = data.get("retry_count")
    if isinstance(retry_count, int) and not isinstance(retry_count, bool) and 0 <= retry_count <= 10:
        projected["retry_count"] = retry_count

    outcome = data.get("outcome")
    if isinstance(outcome, str) and _OUTCOME_RE.fullmatch(outcome):
        projected["outcome"] = outcome

    status_code = _validate_status_code(data.get("status_code"))
    if status_code is not None:
        projected["status_code"] = status_code

    return projected


def _build_log_breadcrumb(
    fields: dict[str, Any],
    level: str,
    category: str,
    timestamp: Any,
) -> dict[str, Any]:
    """Rebuild a breadcrumb solely from validated, code-owned fields."""
    crumb: dict[str, Any] = {
        "type": "log",
        "level": level,
        "category": category,
        "message": fields["operation"],
        "data": fields,
    }
    timestamp = _normalize_timestamp(timestamp)
    if timestamp is not None:
        crumb["timestamp"] = timestamp
    return crumb


def _sanitize_breadcrumb(crumb: Any, hint: dict[str, Any]) -> "dict[str, Any] | None":
    """Admit only marked runestone warning/error records as breadcrumbs.

    The whole body is wrapped so no exception can ever escape: sentry-sdk
    2.68.1 fails open on a raising ``before_breadcrumb`` and would retain the
    original unsanitized breadcrumb. This callback must not log, because a log
    emission would recurse back into the SDK.
    """
    try:
        record = hint.get("log_record") if isinstance(hint, dict) else None
        if not isinstance(record, logging.LogRecord):
            return None
        if not _is_runestone_logger(record.name):
            return None
        level = _RECORD_LEVEL_TO_BREADCRUMB.get(record.levelno)
        if level is None:
            return None
        fields = _project_telemetry_fields(getattr(record, "runestone_telemetry", None))
        if fields is None:
            return None
        timestamp = crumb.get("timestamp") if isinstance(crumb, dict) else None
        return _build_log_breadcrumb(fields, level, record.name, timestamp)
    except Exception:
        return None


def _project_event_breadcrumb(crumb: Any) -> "dict[str, Any] | None":
    """Re-validate a serialized breadcrumb before export.

    This repeats the breadcrumb contract on the event payload so later SDK
    processing cannot bypass the admission policy.
    """
    if not isinstance(crumb, dict) or crumb.get("type") != "log":
        return None

    level = crumb.get("level")
    if not isinstance(level, str) or level not in _BREADCRUMB_LEVELS:
        return None

    category = crumb.get("category")
    if not isinstance(category, str) or not _is_runestone_logger(category):
        return None

    message = crumb.get("message")
    if not isinstance(message, str) or not _OPERATION_RE.fullmatch(message):
        return None

    fields = _project_telemetry_fields(crumb.get("data"))
    if fields is None or fields["operation"] != message:
        return None

    return _build_log_breadcrumb(fields, level, category, crumb.get("timestamp"))


def _project_event(event: Any) -> dict[str, Any]:
    """Rebuild an event from the export allowlist; unknown fields never survive."""
    if not isinstance(event, dict):
        raise TypeError("event must be a mapping")

    projected: dict[str, Any] = {}

    event_id = event.get("event_id")
    if isinstance(event_id, str) and _EVENT_ID_RE.fullmatch(event_id):
        projected["event_id"] = event_id

    if _validate_number(event.get("timestamp")) is not None:
        try:
            projected["timestamp"] = datetime.fromtimestamp(event["timestamp"], tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            pass

    if event.get("platform") == "python":
        projected["platform"] = "python"

    level = event.get("level")
    if isinstance(level, str) and level in _LEVELS:
        projected["level"] = level

    logger_name = event.get("logger")
    if _is_runestone_logger(logger_name):
        projected["logger"] = logger_name

    release = event.get("release")
    if isinstance(release, str) and _RELEASE_RE.fullmatch(release):
        projected["release"] = release

    environment = event.get("environment")
    if isinstance(environment, str) and _ENVIRONMENT_RE.fullmatch(environment):
        projected["environment"] = environment

    exception = event.get("exception")
    if isinstance(exception, dict):
        exception_values = _project_exception_values(exception.get("values"))
        if exception_values is not None:
            projected["exception"] = {"values": exception_values}

    request = event.get("request")
    if isinstance(request, dict):
        method = request.get("method")
        if isinstance(method, str) and _METHOD_RE.fullmatch(method):
            projected["request"] = {"method": method}

    transaction_info = event.get("transaction_info")
    source = transaction_info.get("source") if isinstance(transaction_info, dict) else None
    if source in ("route", "component"):
        route_template = _validate_route_template(event.get("transaction"))
        if route_template is not None:
            projected["transaction"] = route_template

    contexts = event.get("contexts")
    if isinstance(contexts, dict) and isinstance(contexts.get("runestone"), dict):
        status_code = _validate_status_code(contexts["runestone"].get("status_code"))
        if status_code is not None:
            projected["contexts"] = {"runestone": {"status_code": status_code}}

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        values: list[dict[str, Any]] = []
        for crumb in breadcrumbs["values"]:
            projected_crumb = _project_event_breadcrumb(crumb)
            if projected_crumb is not None:
                values.append(projected_crumb)
            if len(values) == _MAX_BREADCRUMBS:
                break
        if values:
            projected["breadcrumbs"] = {"values": values}

    return projected


def _sanitize_event(event: Any, hint: dict[str, Any]) -> "dict[str, Any] | None":
    """Drop the event unless it projects cleanly and serializes under the cap.

    Returns ``None`` on over-cap payloads or any unexpected failure; the
    failure path must not log, because a log emission would recurse back into
    the SDK.
    """
    try:
        projected = _project_event(event)
        serialized = json.dumps(projected, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > _MAX_EVENT_BYTES:
            return None
        return projected
    except Exception:
        return None


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
        auto_session_tracking=False,
        enable_logs=False,
        before_send=cast("EventProcessor", _sanitize_event),
        before_breadcrumb=cast("BreadcrumbProcessor", _sanitize_breadcrumb),
        max_breadcrumbs=20,
        integrations=[
            LoggingIntegration(
                level=logging.WARNING,
                event_level=None,
                sentry_logs_level=None,
                capture_sentry_logs=False,
            )
        ],
    )
