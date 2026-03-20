"""
Observability helpers for lightweight timing instrumentation.
"""

from __future__ import annotations

import inspect
import logging
import time
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

TimingFieldsFactory = Callable[[tuple[Any, ...], dict[str, Any], Any | None, BaseException | None], dict[str, Any]]


def elapsed_ms_since(started: float) -> int:
    """Return elapsed milliseconds from a monotonic start timestamp."""
    return int((time.monotonic() - started) * 1000)


def timed_operation(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    failure_level: int = logging.WARNING,
    fields_factory: TimingFieldsFactory | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorate a sync or async function and log its execution latency.

    The log line always includes `latency_ms` plus any extra fields returned by
    `fields_factory`.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                started = time.monotonic()
                result: Any | None = None
                error: BaseException | None = None
                try:
                    result = await func(*args, **kwargs)
                    return result
                except BaseException as exc:
                    error = exc
                    raise
                finally:
                    _log_timing(
                        logger=logger,
                        message=message,
                        started=started,
                        level=level,
                        failure_level=failure_level,
                        fields_factory=fields_factory,
                        args=args,
                        kwargs=kwargs,
                        result=result,
                        error=error,
                    )

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = time.monotonic()
            result: Any | None = None
            error: BaseException | None = None
            try:
                result = func(*args, **kwargs)
                return result
            except BaseException as exc:
                error = exc
                raise
            finally:
                _log_timing(
                    logger=logger,
                    message=message,
                    started=started,
                    level=level,
                    failure_level=failure_level,
                    fields_factory=fields_factory,
                    args=args,
                    kwargs=kwargs,
                    result=result,
                    error=error,
                )

        return sync_wrapper

    return decorator


def _log_timing(
    *,
    logger: logging.Logger,
    message: str,
    started: float,
    level: int,
    failure_level: int,
    fields_factory: TimingFieldsFactory | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any | None,
    error: BaseException | None,
) -> None:
    latency_ms = elapsed_ms_since(started)
    fields = {"latency_ms": latency_ms}
    if fields_factory is not None:
        extra_fields = fields_factory(args, kwargs, result, error) or {}
        fields.update({key: value for key, value in extra_fields.items() if value is not None})
    if error is not None:
        fields["outcome"] = "error"
        fields["error_type"] = type(error).__name__
    else:
        fields["outcome"] = "success"
    log_level = failure_level if error is not None else level
    logger.log(log_level, "%s %s", message, _format_fields(fields))


def _format_fields(fields: dict[str, Any]) -> str:
    return " ".join(f"{key}={value}" for key, value in fields.items())
