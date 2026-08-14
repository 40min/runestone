"""In-memory operation accounting with async-context isolation and safe logs."""

import asyncio
import json
import logging
import threading
import uuid
from contextlib import AbstractAsyncContextManager, AbstractContextManager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Generator, Mapping

from runestone.model_costs.pricing import DEFAULT_PRICE_PATH, PriceSnapshot, load_price_snapshot, model_price_key

logger = logging.getLogger(__name__)

COST_QUALITY_EXACT = "exact"
COST_QUALITY_ESTIMATED = "estimated"
COST_QUALITY_UNKNOWN = "unknown"
TERMINAL_CHILD_ERRORS = {"failed", "timed_out", "cancelled", "stale_replaced", "cancelled_with_unknown_usage"}
NEUTRAL_CHILD_STATUSES = {"completed", "skipped_no_websocket"}
DEGRADED_INTERACTION_STATUSES = {
    "cancelled",
    "cancelled_with_unknown_usage",
    "completed_with_errors",
    "failed",
    "stale_replaced",
    "timed_out",
}


@dataclass(frozen=True)
class CostCalculation:
    """The known subtotal and confidence produced for one paid interaction."""

    known_cost_usd: Decimal
    cost_quality: str
    cost_source: str
    applied_rates_usd: Mapping[str, Decimal]


@dataclass(frozen=True)
class InteractionRecord:
    """Content-free accounting metadata for one provider interaction."""

    operation_id: str
    operation_type: str
    component: str
    phase: str
    provider: str
    model: str
    status: str
    usage: Mapping[str, Decimal]
    known_cost_usd: Decimal
    cost_quality: str
    cost_source: str
    applied_rates_usd: Mapping[str, Decimal]


@dataclass(frozen=True)
class _TrackingBinding:
    """The operation and immutable phase bound to the current async context."""

    collector: "_CostCollector"
    phase: str


_current_binding: ContextVar[_TrackingBinding | None] = ContextVar("model_cost_context", default=None)


def _as_decimal(value: object, *, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return result


def normalize_usage(usage: Mapping[str, object] | None) -> dict[str, Decimal]:
    """Convert provider quantities to non-negative Decimals without arithmetic on floats."""
    if usage is None:
        return {}
    normalized: dict[str, Decimal] = {}
    for unit, quantity in usage.items():
        if not isinstance(unit, str) or not unit:
            raise ValueError("Usage unit must be a non-empty string")
        normalized[unit] = _as_decimal(quantity, field=f"usage.{unit}")
    return normalized


def calculate_cost(
    provider: str,
    model: str,
    usage: Mapping[str, object] | None,
    *,
    provider_cost_usd: object | None = None,
    snapshot: PriceSnapshot | None = None,
) -> CostCalculation:
    """Calculate one interaction cost, preferring provider-reported request cost."""
    if provider_cost_usd is not None:
        return CostCalculation(
            known_cost_usd=_as_decimal(provider_cost_usd, field="provider_cost_usd"),
            cost_quality=COST_QUALITY_EXACT,
            cost_source="provider_response",
            applied_rates_usd={},
        )

    normalized_usage = normalize_usage(usage)
    if not normalized_usage:
        return CostCalculation(Decimal("0"), COST_QUALITY_UNKNOWN, "unknown", {})
    if snapshot is None:
        return CostCalculation(Decimal("0"), COST_QUALITY_UNKNOWN, "unknown", {})
    price = snapshot.models.get(model_price_key(provider, model))
    if price is None:
        return CostCalculation(Decimal("0"), COST_QUALITY_UNKNOWN, "unknown", {})

    known_cost = Decimal("0")
    has_unknown_rate = False
    applied_rates: dict[str, Decimal] = {}
    for unit, quantity in normalized_usage.items():
        rate = price.rates_usd.get(unit)
        if rate is None:
            if quantity != 0:
                has_unknown_rate = True
            continue
        applied_rates[unit] = rate
        known_cost += quantity * rate
    return CostCalculation(
        known_cost_usd=known_cost,
        cost_quality=COST_QUALITY_UNKNOWN if has_unknown_rate else COST_QUALITY_ESTIMATED,
        cost_source="unknown" if has_unknown_rate else price.source,
        applied_rates_usd=applied_rates,
    )


def aggregate_quality(records: tuple[InteractionRecord, ...] | list[InteractionRecord]) -> str:
    """Return the least-certain interaction quality in an aggregate."""
    if any(record.cost_quality == COST_QUALITY_UNKNOWN for record in records):
        return COST_QUALITY_UNKNOWN
    if any(record.cost_quality == COST_QUALITY_ESTIMATED for record in records):
        return COST_QUALITY_ESTIMATED
    return COST_QUALITY_EXACT


def _summary_quality(
    records: tuple[InteractionRecord, ...] | list[InteractionRecord], *, unknown_children: int = 0
) -> str:
    if unknown_children:
        return COST_QUALITY_UNKNOWN
    return aggregate_quality(records)


def _record_counts(records: tuple[InteractionRecord, ...] | list[InteractionRecord]) -> dict[str, int]:
    return {
        "exact_calls": sum(record.cost_quality == COST_QUALITY_EXACT for record in records),
        "estimated_calls": sum(record.cost_quality == COST_QUALITY_ESTIMATED for record in records),
        "unknown_calls": sum(record.cost_quality == COST_QUALITY_UNKNOWN for record in records),
    }


def _summary_counts(
    records: tuple[InteractionRecord, ...] | list[InteractionRecord], *, unknown_children: int = 0
) -> dict[str, int]:
    counts = _record_counts(records)
    counts["unknown_calls"] += unknown_children
    return counts


def _known_total(records: tuple[InteractionRecord, ...] | list[InteractionRecord]) -> Decimal:
    return sum((record.known_cost_usd for record in records), start=Decimal("0"))


def _format_usd(value: Decimal) -> str:
    """Render USD amounts consistently while preserving Decimal arithmetic internally."""
    return format(value, ".8f")


def _render_usd_map(values: Mapping[str, Decimal]) -> str:
    return json.dumps({key: _format_usd(value) for key, value in sorted(values.items())}, separators=(",", ":"))


def _cost_breakdown(records: tuple[InteractionRecord, ...] | list[InteractionRecord]) -> str:
    totals: dict[str, Decimal] = {}
    for record in records:
        totals[record.component] = totals.get(record.component, Decimal("0")) + record.known_cost_usd
    return _render_usd_map(totals)


def _safe_log(level: int, message: str, *args: object) -> None:
    try:
        logger.log(level, message, *args)
    except Exception as exc:  # pragma: no cover - the fallback itself must never escape
        try:
            logger.warning("Model cost logging failed error=%s", exc)
        except Exception:
            pass


def _render_fields(fields: Mapping[str, object]) -> str:
    return " ".join(f"{key}={value}" for key, value in fields.items())


class CostTrackingHandle:
    """Transfer ambient model-cost tracking to one background segment."""

    def __init__(self, collector: "_CostCollector", name: str) -> None:
        self._collector = collector
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> str | None:
        return self._collector.handle_status(self._name)

    def activate(self) -> AbstractContextManager[None]:
        """Bind the parent collector to this synchronous background context."""
        return _bind_collector(self._collector, "background")

    def finish(self, status: str) -> bool:
        """Finish this handle once, emitting a correction when it is the last."""
        return self._collector.finish_handle(self._name, status)


class _CostCollector:
    """Own interactions, transferred segments, and summary state for one activity."""

    def __init__(
        self,
        operation_type: str,
        *,
        operation_id: str | None = None,
        snapshot: PriceSnapshot | None = None,
        price_path: str | Path = DEFAULT_PRICE_PATH,
    ) -> None:
        self.operation_type = operation_type
        self.operation_id = operation_id or str(uuid.uuid4())
        self.snapshot = snapshot if snapshot is not None else load_price_snapshot(price_path)
        self._interactions: list[InteractionRecord] = []
        self._children: dict[str, str | None] = {}
        self._state = "foreground_open"
        self._preliminary_records: tuple[InteractionRecord, ...] | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def interactions(self) -> tuple[InteractionRecord, ...]:
        with self._lock:
            return tuple(self._interactions)

    @property
    def children(self) -> Mapping[str, str | None]:
        with self._lock:
            return dict(self._children)

    def transfer(self, name: str) -> CostTrackingHandle:
        """Register an expected background segment before scheduling it."""
        if not isinstance(name, str) or not name:
            raise ValueError("Handle name must be a non-empty string")
        with self._lock:
            if name not in self._children and self._state not in {"corrected_emitted", "final_failed", "final_emitted"}:
                self._children[name] = None
            elif name not in self._children:
                _safe_log(
                    logging.WARNING,
                    "Model cost handle registration ignored operation_id=%s handle=%s state=%s",
                    self.operation_id,
                    name,
                    self._state,
                )
        return CostTrackingHandle(self, name)

    def handle_status(self, name: str) -> str | None:
        with self._lock:
            return self._children.get(name)

    def finish_handle(self, name: str, status: str) -> bool:
        """Record one allowed terminal status and emit correction when eligible."""
        allowed = TERMINAL_CHILD_ERRORS | NEUTRAL_CHILD_STATUSES
        if status not in allowed:
            raise ValueError(f"Invalid handle status: {status}")
        should_correct = False
        with self._lock:
            if self._state in {"corrected_emitted", "final_failed", "final_emitted"}:
                return False
            if name not in self._children:
                _safe_log(
                    logging.WARNING,
                    "Model cost unregistered handle finish ignored operation_id=%s handle=%s",
                    self.operation_id,
                    name,
                )
                return False
            if self._children[name] is not None:
                return False
            self._children[name] = status
            should_correct = self._state == "preliminary_emitted" and self._all_children_closed_unlocked()
        if should_correct:
            self.emit_corrected()
        return True

    def seal_open_children(self, status: str = "cancelled_with_unknown_usage") -> None:
        """Seal every still-open child so late callbacks can be ignored safely."""
        with self._lock:
            for name, child_status in self._children.items():
                if child_status is None:
                    self._children[name] = status

    def record(
        self,
        *,
        component: str,
        phase: str,
        provider: str,
        model: str,
        status: str,
        usage: Mapping[str, object] | None = None,
        provider_cost_usd: object | None = None,
    ) -> InteractionRecord | None:
        """Record one interaction and swallow malformed tracking metadata."""
        try:
            normalized_usage = normalize_usage(usage)
            calculation = calculate_cost(
                provider,
                model,
                normalized_usage,
                provider_cost_usd=provider_cost_usd,
                snapshot=self.snapshot,
            )
            record = InteractionRecord(
                operation_id=self.operation_id,
                operation_type=self.operation_type,
                component=component,
                phase=phase,
                provider=provider,
                model=model,
                status=status,
                usage=normalized_usage,
                known_cost_usd=calculation.known_cost_usd,
                cost_quality=calculation.cost_quality,
                cost_source=calculation.cost_source,
                applied_rates_usd=calculation.applied_rates_usd,
            )
            with self._lock:
                if self._state in {"corrected_emitted", "final_failed", "final_emitted"}:
                    return None
                self._interactions.append(record)
            _safe_log(
                logging.DEBUG,
                "model_cost_interaction %s",
                _render_fields(
                    {
                        "operation": record.operation_type,
                        "operation_id": record.operation_id,
                        "component": record.component,
                        "phase": record.phase,
                        "provider": record.provider,
                        "model": record.model,
                        "status": record.status,
                        "usage": json.dumps({key: str(value) for key, value in sorted(record.usage.items())}),
                        "known_cost_usd": _format_usd(record.known_cost_usd),
                        "cost_quality": record.cost_quality,
                        "cost_source": record.cost_source,
                        "applied_rates_usd": _render_usd_map(record.applied_rates_usd),
                    }
                ),
            )
            return record
        except Exception as exc:
            _safe_log(
                logging.WARNING,
                "Model cost interaction recording failed operation_id=%s component=%s error=%s",
                self.operation_id,
                component,
                exc,
            )
            return None

    def emit_preliminary(self) -> Mapping[str, object] | None:
        """Freeze and log foreground records, then allow a ready correction."""
        should_correct = False
        with self._lock:
            if self._state != "foreground_open":
                return None
            self._preliminary_records = tuple(record for record in self._interactions if record.phase == "foreground")
            fields: dict[str, object] = {
                "stage": "preliminary",
                "operation": self.operation_type,
                "operation_id": self.operation_id,
                "status": "foreground_complete",
                "known_foreground_usd": _format_usd(_known_total(self._preliminary_records)),
                "cost_breakdown_usd": _cost_breakdown(self._preliminary_records),
                "cost_quality": aggregate_quality(self._preliminary_records),
                "background": "pending",
                **_record_counts(self._preliminary_records),
            }
            self._state = "preliminary_emitted"
            should_correct = bool(self._children) and self._all_children_closed_unlocked()
        _safe_log(logging.INFO, "model_cost %s", _render_fields(fields))
        if should_correct:
            self.emit_corrected()
        return fields

    def emit_corrected(self) -> Mapping[str, object] | None:
        """Log exactly one corrected chat summary after all children close."""
        with self._lock:
            if self._state != "preliminary_emitted" or not self._all_children_closed_unlocked():
                return None
            preliminary = self._preliminary_records or ()
            all_records = tuple(self._interactions)
            background = tuple(record for record in all_records if record.phase == "background")
            has_child_error = any(status in TERMINAL_CHILD_ERRORS for status in self._children.values())
            unknown_children = self._unknown_usage_children_unlocked()
            fields: dict[str, object] = {
                "stage": "corrected",
                "operation": self.operation_type,
                "operation_id": self.operation_id,
                "status": "completed_with_errors" if has_child_error else "completed",
                "post_turn_status": self._children.get("post_turn", "not_requested"),
                "tts_status": self._children.get("tts", "not_requested"),
                "known_foreground_usd": _format_usd(_known_total(preliminary)),
                "known_background_usd": _format_usd(_known_total(background)),
                "known_total_usd": _format_usd(_known_total(all_records)),
                "known_delta_usd": _format_usd(_known_total(background)),
                "cost_breakdown_usd": _cost_breakdown(all_records),
                "cost_quality": _summary_quality(all_records, unknown_children=unknown_children),
                **_summary_counts(all_records, unknown_children=unknown_children),
            }
            self._state = "corrected_emitted"
        _safe_log(logging.INFO, "model_cost %s", _render_fields(fields))
        return fields

    def emit_final(self, status: str = "completed") -> Mapping[str, object] | None:
        """Seal and log the canonical one-summary non-chat operation result."""
        with self._lock:
            if self._state in {"corrected_emitted", "final_failed", "final_emitted"}:
                return None
            records = tuple(self._interactions)
            unknown_children = self._unknown_usage_children_unlocked()
            fields: dict[str, object] = {
                "stage": "final",
                "operation": self.operation_type,
                "operation_id": self.operation_id,
                "status": status,
                "known_total_usd": _format_usd(_known_total(records)),
                "cost_breakdown_usd": _cost_breakdown(records),
                "cost_quality": _summary_quality(records, unknown_children=unknown_children),
                **_summary_counts(records, unknown_children=unknown_children),
            }
            self._state = "final_failed" if status == "failed" else "final_emitted"
        _safe_log(logging.INFO, "model_cost %s", _render_fields(fields))
        return fields

    def ordinary_completion_status(self) -> str:
        """Return the final status inferred for a successful ordinary scope exit."""
        with self._lock:
            if any(record.status in DEGRADED_INTERACTION_STATUSES for record in self._interactions):
                return "completed_with_errors"
            return "completed"

    def emit_failed(self) -> Mapping[str, object] | None:
        """Emit the single chat failure summary and suppress other stages."""
        self.seal_open_children()
        return self.emit_final(status="failed")

    def _all_children_closed_unlocked(self) -> bool:
        return all(status is not None for status in self._children.values())

    def _unknown_usage_children_unlocked(self) -> int:
        return sum(status == "cancelled_with_unknown_usage" for status in self._children.values())


class _OrdinaryCostScope(AbstractAsyncContextManager[None]):
    """Own one ordinary summary or inherit the active collector fail-open."""

    def __init__(self, activity: str) -> None:
        parent_binding = _current_binding.get()
        self._owned = parent_binding is None
        self._collector = _CostCollector(activity) if self._owned else parent_binding.collector
        self._phase = "foreground" if self._owned else parent_binding.phase
        self._token: Token[_TrackingBinding | None] | None = None
        if parent_binding is not None:
            _safe_log(
                logging.WARNING,
                "Model cost nested tracking inherited active collector requested_activity=%s " "active_activity=%s",
                activity,
                parent_binding.collector.operation_type,
            )

    async def __aenter__(self) -> None:
        self._token = _current_binding.set(_TrackingBinding(self._collector, self._phase))

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: object
    ) -> None:
        if self._token is not None:
            _current_binding.reset(self._token)
        if self._owned:
            status = self._terminal_status(exc_type)
            if status == "completed":
                status = self._collector.ordinary_completion_status()
            self._collector.emit_final(status=status)

    @staticmethod
    def _terminal_status(exc_type: type[BaseException] | None) -> str:
        if exc_type is None:
            return "completed"
        if issubclass(exc_type, asyncio.CancelledError):
            return "cancelled"
        if issubclass(exc_type, (TimeoutError, asyncio.TimeoutError)):
            return "timed_out"
        return "failed"


class _BackgroundCostScope(AbstractAsyncContextManager["_BackgroundController"]):
    """Own the foreground-to-background summary lifecycle."""

    def __init__(self, activity: str) -> None:
        self._collector = _CostCollector(activity)
        self._controller = _BackgroundController(self._collector)
        self._token: Token[_TrackingBinding | None] | None = None

    async def __aenter__(self) -> "_BackgroundController":
        self._token = _current_binding.set(_TrackingBinding(self._collector, "foreground"))
        return self._controller

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: object
    ) -> None:
        if self._token is not None:
            _current_binding.reset(self._token)
        if exc_type is None:
            self._collector.emit_preliminary()
        else:
            self._collector.emit_failed()


class _BackgroundController:
    """Create public handles without exposing the collector."""

    def __init__(self, collector: _CostCollector) -> None:
        self._collector = collector

    def transfer(self, name: str) -> CostTrackingHandle:
        return self._collector.transfer(name)


def track_model_costs(activity: str) -> _OrdinaryCostScope:
    """Track one awaited operation and automatically emit exactly one final summary.

    Nested calls inherit the active collector, warn without content, and do not summarize.
    """
    return _OrdinaryCostScope(activity)


def track_model_costs_with_background(activity: str) -> _BackgroundCostScope:
    """Track foreground work and explicit transferred background segments."""
    return _BackgroundCostScope(activity)


@contextmanager
def suspend_model_cost_tracking() -> Generator[None]:
    """Temporarily clear ambient model-cost tracking for detached work creation."""
    token: Token[_TrackingBinding | None] = _current_binding.set(None)
    try:
        yield
    finally:
        _current_binding.reset(token)


@contextmanager
def _bind_collector(collector: _CostCollector, phase: str) -> Generator[None]:
    token: Token[_TrackingBinding | None] = _current_binding.set(_TrackingBinding(collector, phase))
    try:
        yield
    finally:
        _current_binding.reset(token)


def record_model_interaction(
    component: str,
    provider: str,
    model: str,
    status: str,
    usage: Mapping[str, object] | None = None,
    provider_cost_usd: object | None = None,
) -> InteractionRecord | None:
    """Fail-open recorder used by callbacks and direct provider clients."""
    try:
        binding = _current_binding.get()
        if binding is None:
            _safe_log(
                logging.WARNING,
                "Model cost interaction ignored without active operation "
                "component=%s provider=%s model=%s status=%s",
                component,
                provider,
                model,
                status,
            )
            return None
        return binding.collector.record(
            component=component,
            phase=binding.phase,
            provider=provider,
            model=model,
            status=status,
            usage=usage,
            provider_cost_usd=provider_cost_usd,
        )
    except Exception as exc:  # pragma: no cover - defensive public boundary
        _safe_log(logging.WARNING, "Model cost recording failed component=%s error=%s", component, exc)
        return None
