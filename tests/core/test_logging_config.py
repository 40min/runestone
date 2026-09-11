import logging
from io import StringIO

import pytest

from runestone.core import logging_config


@pytest.fixture
def bound_request_id():
    """Bind a correlation ID for the current test task and reset it after."""
    token = logging_config.set_current_request_id("a" * 32)
    yield "a" * 32
    logging_config.reset_current_request_id(token)


def test_resolve_color_setting_truthy(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "on")
    assert logging_config._resolve_color_setting() is True


def test_resolve_color_setting_falsy(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "off")
    assert logging_config._resolve_color_setting() is False


def test_resolve_color_setting_auto(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "auto")
    assert logging_config._resolve_color_setting() is None


def test_log_filter_strips_leading_tag_and_sets_producer():
    record = logging.LogRecord(
        name="runestone.api.endpoints",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="[API] Analysis request received",
        args=(),
        exc_info=None,
    )
    log_filter = logging_config.RunestoneLogFilter()
    accepted = log_filter.filter(record)

    assert accepted is True
    assert record.producer == "api.endpoints"
    assert record.msg == "Analysis request received"


def test_log_filter_attaches_bound_request_id(bound_request_id):
    record = logging.LogRecord(
        name="runestone.api.endpoints",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Analysis request received",
        args=(),
        exc_info=None,
    )
    logging_config.RunestoneLogFilter().filter(record)

    assert record.request_id == bound_request_id


def test_log_filter_attaches_no_request_id_outside_requests():
    record = logging.LogRecord(
        name="runestone.api.endpoints",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Analysis request received",
        args=(),
        exc_info=None,
    )
    logging_config.RunestoneLogFilter().filter(record)

    assert record.request_id is None


def test_formatter_renders_request_id_suffix(bound_request_id):
    record = logging.LogRecord(
        name="runestone.api.endpoints",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Analysis request received",
        args=(),
        exc_info=None,
    )
    logging_config.RunestoneLogFilter().filter(record)
    rendered = logging_config.RunestoneLogFormatter("%(message)s").format(record)

    assert rendered == f"Analysis request received | request_id={bound_request_id}"


def test_formatter_omits_suffix_outside_requests():
    record = logging.LogRecord(
        name="runestone.api.endpoints",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Analysis request received",
        args=(),
        exc_info=None,
    )
    logging_config.RunestoneLogFilter().filter(record)
    rendered = logging_config.RunestoneLogFormatter("%(message)s").format(record)

    assert rendered == "Analysis request received"
    assert "request_id=" not in rendered


def test_setup_logging_installs_request_id_formatter(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "auto")
    monkeypatch.setattr(logging_config.sys, "stdout", StringIO())
    logging_config.setup_logging(level="INFO")

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, logging_config.RunestoneLogFormatter)


def test_setup_logging_forces_color_handler_when_enabled(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "1")
    logging_config.setup_logging(level="INFO")

    root = logging.getLogger()
    rich_handlers = [handler for handler in root.handlers if isinstance(handler, logging_config.RichHandler)]
    assert len(rich_handlers) == 1
    assert rich_handlers[0].console.is_terminal is True


def test_setup_logging_uses_stream_handler_in_auto_non_tty(monkeypatch):
    monkeypatch.setenv("RUNESTONE_LOG_COLOR", "auto")
    monkeypatch.setattr(logging_config.sys, "stdout", StringIO())
    logging_config.setup_logging(level="INFO")

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)
    assert not isinstance(root.handlers[0], logging_config.RichHandler)
