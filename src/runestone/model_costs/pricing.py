"""Local model-price snapshots and conservative source normalization."""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

import httpx

from runestone.config import PAID_AGENT_NAMES, Settings

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_PRICE_PATH = Path("state/model_prices.json")
MODELS_DEV_URL = "https://models.dev/api.json"
PORTKEY_URL_TEMPLATE = "https://configs.portkey.ai/pricing/{provider}.json"
REQUEST_TIMEOUT_SECONDS = 20.0
MODELS_DEV_MAX_BYTES = 25 * 1024 * 1024
PORTKEY_MAX_BYTES = 5 * 1024 * 1024
SOURCE_PROVIDER_NAMES = {
    "openai": "openai",
    "openrouter": "openrouter",
    "gemini": "google",
}

MODELS_DEV_RATE_FIELDS = {
    "input": "input_token",
    "output": "output_token",
    "cache_read": "cached_input_token",
    "cache_write": "cached_input_write_token",
    "reasoning": "reasoning_token",
    "input_audio": "input_audio_token",
    "output_audio": "output_audio_token",
}
PORTKEY_RATE_FIELDS = {
    "request_token": "input_token",
    "response_token": "output_token",
    "cache_read_input_token": "cached_input_token",
    "cache_write_input_token": "cached_input_write_token",
    "request_audio_token": "input_audio_token",
    "response_audio_token": "output_audio_token",
}


class PriceSnapshotError(ValueError):
    """Raised when a price source or local snapshot violates its contract."""


@dataclass(frozen=True, order=True)
class ConfiguredModel:
    """A provider/model route that Runestone can send paid work through."""

    provider: str
    model: str

    @property
    def key(self) -> str:
        return model_price_key(self.provider, self.model)


@dataclass(frozen=True)
class ModelPrice:
    """Validated normalized prices for one provider/model route."""

    source: str
    source_url: str | None
    source_model_id: str
    last_successful_at: str | None
    stale: bool
    rates_usd: Mapping[str, Decimal]


@dataclass(frozen=True)
class PriceSnapshot:
    """Validated immutable view of the local price registry."""

    fetched_at: str
    models: Mapping[str, ModelPrice]
    schema_version: int = SCHEMA_VERSION

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "fetched_at": self.fetched_at,
            "models": {
                key: {
                    "source": entry.source,
                    "source_url": entry.source_url,
                    "source_model_id": entry.source_model_id,
                    "last_successful_at": entry.last_successful_at,
                    "stale": entry.stale,
                    "rates_usd": {unit: str(rate) for unit, rate in sorted(entry.rates_usd.items())},
                }
                for key, entry in sorted(self.models.items())
            },
        }


@dataclass(frozen=True)
class RefreshCounts:
    """Operator-safe refresh result containing counts but no source payloads."""

    models_dev: int
    portkey: int
    stale: int
    manual: int
    unknown: int


def utc_now_string() -> str:
    """Return a stable UTC timestamp suitable for snapshot metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def model_price_key(provider: str, model: str) -> str:
    """Return the registry key for the route actually used by Runestone."""
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    if not normalized_provider or not normalized_model:
        raise PriceSnapshotError("Provider and model must be non-empty")
    return f"{normalized_provider}/{normalized_model}"


def resolve_configured_models(settings: Settings) -> set[ConfiguredModel]:
    """Resolve every configured paid provider/model pair without side effects."""
    configured: set[ConfiguredModel] = set()

    def add(provider: str | None, model: str | None) -> None:
        if provider and model:
            configured.add(ConfiguredModel(provider.strip().lower(), model.strip()))

    for agent_name in PAID_AGENT_NAMES:
        if agent_name == "teacher_backup" and not settings.teacher_backup_model:
            continue
        agent = settings.get_agent_llm_settings(agent_name)
        add(agent.provider, agent.model)

    service_provider = settings.resolve_service_llm_provider()
    add(service_provider, settings.resolve_service_llm_model(provider=service_provider))
    add(settings.resolve_ocr_llm_provider(), settings.resolve_ocr_llm_model())
    add(settings.voice_transcription_provider, settings.voice_transcription_model)
    add("openai", settings.voice_enhancement_model)
    if settings.tts_provider == "openai":
        add("openai", settings.tts_model)
    elif settings.tts_provider == "elevenlabs":
        add("elevenlabs", settings.elevenlabs_tts_model)

    return configured


def source_provider_name(provider: str) -> str | None:
    """Map a Runestone provider name to pricing-source provider identity."""
    return SOURCE_PROVIDER_NAMES.get(provider.strip().lower())


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise PriceSnapshotError(f"{field} must be a decimal value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise PriceSnapshotError(f"{field} must be a decimal value") from exc
    if not result.is_finite() or result < 0:
        raise PriceSnapshotError(f"{field} must be a finite non-negative decimal")
    return result


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PriceSnapshotError(f"{field} must be a non-empty string")
    return value.strip()


def _snapshot_decimal(value: object, field: str) -> Decimal:
    """Parse money from the local JSON contract, where decimals are strings."""
    if not isinstance(value, str):
        raise PriceSnapshotError(f"{field} must be a decimal string")
    return _decimal(value, field)


def validate_snapshot(payload: object) -> PriceSnapshot:
    """Validate a decoded local snapshot before it can become active."""
    if not isinstance(payload, dict):
        raise PriceSnapshotError("Price snapshot must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PriceSnapshotError(f"Unsupported price snapshot schema_version: {payload.get('schema_version')!r}")
    fetched_at = _required_string(payload.get("fetched_at"), "fetched_at")
    raw_models = payload.get("models")
    if not isinstance(raw_models, dict):
        raise PriceSnapshotError("models must be an object")

    models: dict[str, ModelPrice] = {}
    for key, raw_entry in raw_models.items():
        if not isinstance(key, str) or "/" not in key:
            raise PriceSnapshotError("Every model key must be provider/model")
        if not isinstance(raw_entry, dict):
            raise PriceSnapshotError(f"Model entry {key!r} must be an object")
        source = _required_string(raw_entry.get("source"), f"{key}.source")
        source_url = raw_entry.get("source_url")
        if source_url is not None and not isinstance(source_url, str):
            raise PriceSnapshotError(f"{key}.source_url must be a string or null")
        source_model_id = _required_string(raw_entry.get("source_model_id"), f"{key}.source_model_id")
        last_successful_at = raw_entry.get("last_successful_at")
        if last_successful_at is not None and not isinstance(last_successful_at, str):
            raise PriceSnapshotError(f"{key}.last_successful_at must be a string or null")
        stale = raw_entry.get("stale")
        if not isinstance(stale, bool):
            raise PriceSnapshotError(f"{key}.stale must be boolean")
        raw_rates = raw_entry.get("rates_usd")
        if not isinstance(raw_rates, dict) or not raw_rates:
            raise PriceSnapshotError(f"{key}.rates_usd must be a non-empty object")
        rates: dict[str, Decimal] = {}
        for unit, raw_rate in raw_rates.items():
            if not isinstance(unit, str) or not unit.strip():
                raise PriceSnapshotError(f"{key}.rates_usd contains an invalid unit")
            rates[unit] = _snapshot_decimal(raw_rate, f"{key}.rates_usd.{unit}")
        models[key] = ModelPrice(
            source=source,
            source_url=source_url,
            source_model_id=source_model_id,
            last_successful_at=last_successful_at,
            stale=stale,
            rates_usd=rates,
        )
    return PriceSnapshot(fetched_at=fetched_at, models=models)


def load_price_snapshot(path: str | Path = DEFAULT_PRICE_PATH) -> PriceSnapshot | None:
    """Load a validated local snapshot, failing open with a visible warning."""
    snapshot_path = Path(path)
    try:
        with snapshot_path.open(encoding="utf-8") as stream:
            snapshot = validate_snapshot(json.load(stream))
    except FileNotFoundError:
        logger.warning("Model price snapshot is missing path=%s; costs may be unknown", snapshot_path)
        return None
    except (OSError, json.JSONDecodeError, PriceSnapshotError) as exc:
        logger.warning("Model price snapshot is invalid path=%s error=%s; costs may be unknown", snapshot_path, exc)
        return None

    stale_count = sum(entry.stale for entry in snapshot.models.values())
    if stale_count:
        logger.warning("Model price snapshot contains stale entries path=%s stale=%d", snapshot_path, stale_count)
    return snapshot


def _models_dev_provider(payload: Mapping[str, object], source_provider: str) -> Mapping[str, object] | None:
    raw = payload.get(source_provider)
    return raw if isinstance(raw, dict) else None


def normalize_models_dev(
    payload: object,
    configured: set[ConfiguredModel],
    *,
    fetched_at: str,
) -> dict[str, ModelPrice]:
    """Normalize only explicitly configured routes from a Models.dev payload."""
    if not isinstance(payload, dict):
        raise PriceSnapshotError("Models.dev payload must be an object")
    normalized: dict[str, ModelPrice] = {}
    recognized_provider = False
    for route in sorted(configured):
        source_provider = source_provider_name(route.provider)
        if source_provider is None:
            continue
        provider_payload = _models_dev_provider(payload, source_provider)
        if provider_payload is None:
            continue
        recognized_provider = True
        raw_models = provider_payload.get("models")
        if not isinstance(raw_models, dict):
            raise PriceSnapshotError(f"Models.dev provider {source_provider!r} has no models object")
        raw_model = raw_models.get(route.model)
        if not isinstance(raw_model, dict):
            continue
        source_model_id = raw_model.get("id", route.model)
        if not isinstance(source_model_id, str) or source_model_id != route.model:
            continue
        raw_cost = raw_model.get("cost")
        if not isinstance(raw_cost, dict):
            continue
        rates: dict[str, Decimal] = {}
        for source_field, unit in MODELS_DEV_RATE_FIELDS.items():
            if source_field not in raw_cost or raw_cost[source_field] is None:
                continue
            rates[unit] = _decimal(
                raw_cost[source_field], f"models.dev.{source_provider}.{route.model}.{source_field}"
            ) / Decimal(1_000_000)
        if rates:
            normalized[route.key] = ModelPrice(
                source="models.dev",
                source_url=MODELS_DEV_URL,
                source_model_id=source_model_id,
                last_successful_at=fetched_at,
                stale=False,
                rates_usd=rates,
            )
    if configured and not recognized_provider and any(source_provider_name(route.provider) for route in configured):
        raise PriceSnapshotError("Models.dev payload contains none of the expected configured providers")
    return normalized


def _portkey_models(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, dict):
        raise PriceSnapshotError("Portkey payload must be an object")
    models = payload.get("models")
    if not isinstance(models, dict):
        raise PriceSnapshotError("Portkey models must be an object")
    return models


def normalize_portkey(
    payload: object,
    configured: set[ConfiguredModel],
    *,
    provider: str,
    fetched_at: str,
) -> dict[str, ModelPrice]:
    """Normalize token rates from one provider-specific Portkey payload."""
    source_provider = source_provider_name(provider)
    if source_provider is None:
        return {}
    models = _portkey_models(payload)
    normalized: dict[str, ModelPrice] = {}
    for route in sorted(configured):
        if route.provider != provider:
            continue
        raw_model = models.get(route.model)
        if not isinstance(raw_model, dict):
            continue
        source_model_id = raw_model.get("id", raw_model.get("model", route.model))
        if not isinstance(source_model_id, str) or source_model_id != route.model:
            continue
        pricing_config = raw_model.get("pricing_config")
        if not isinstance(pricing_config, dict):
            continue
        currency = pricing_config.get("currency")
        if currency is not None and currency != "USD":
            raise PriceSnapshotError(f"Portkey model {route.model!r} has unsupported currency")
        pay_as_you_go = pricing_config.get("pay_as_you_go")
        if not isinstance(pay_as_you_go, dict):
            raise PriceSnapshotError(f"Portkey model {route.model!r} has no pay_as_you_go pricing")
        rates: dict[str, Decimal] = {}
        for source_field, unit in PORTKEY_RATE_FIELDS.items():
            raw_unit = pay_as_you_go.get(source_field)
            if raw_unit is None:
                continue
            if not isinstance(raw_unit, dict) or "price" not in raw_unit:
                raise PriceSnapshotError(f"Portkey {route.model!r} unit {source_field!r} has no price")
            rates[unit] = _decimal(
                raw_unit["price"], f"portkey.{source_provider}.{route.model}.{source_field}.price"
            ) / Decimal(100)
        additional_units = pay_as_you_go.get("additional_units")
        if additional_units is not None:
            if not isinstance(additional_units, dict):
                raise PriceSnapshotError(f"Portkey model {route.model!r} additional_units must be an object")
            reasoning = additional_units.get("thinking_token")
            if reasoning is not None:
                if not isinstance(reasoning, dict) or "price" not in reasoning:
                    raise PriceSnapshotError(f"Portkey model {route.model!r} thinking_token has no price")
                rates["reasoning_token"] = _decimal(
                    reasoning["price"], f"portkey.{source_provider}.{route.model}.thinking_token.price"
                ) / Decimal(100)
        if rates:
            normalized[route.key] = ModelPrice(
                source="portkey",
                source_url=PORTKEY_URL_TEMPLATE.format(provider=source_provider),
                source_model_id=source_model_id,
                last_successful_at=fetched_at,
                stale=False,
                rates_usd=rates,
            )
    return normalized


def build_refreshed_snapshot(
    configured: set[ConfiguredModel],
    refreshed: Mapping[str, ModelPrice],
    previous: PriceSnapshot | None,
    *,
    fetched_at: str,
) -> tuple[PriceSnapshot, RefreshCounts]:
    """Merge refreshed entries with manual values and stale configured values."""
    models: dict[str, ModelPrice] = {}
    previous_models = previous.models if previous else {}
    manual_entries = {key: entry for key, entry in previous_models.items() if entry.source == "manual"}
    models.update(manual_entries)

    stale = 0
    unknown = 0
    models_dev = 0
    portkey = 0
    for route in sorted(configured):
        if route.key in manual_entries:
            continue
        fresh_entry = refreshed.get(route.key)
        if fresh_entry is not None:
            models[route.key] = fresh_entry
            if fresh_entry.source == "models.dev":
                models_dev += 1
            elif fresh_entry.source == "portkey":
                portkey += 1
            continue
        previous_entry = previous_models.get(route.key)
        if previous_entry is not None:
            models[route.key] = ModelPrice(
                source=previous_entry.source,
                source_url=previous_entry.source_url,
                source_model_id=previous_entry.source_model_id,
                last_successful_at=previous_entry.last_successful_at,
                stale=True,
                rates_usd=previous_entry.rates_usd,
            )
            stale += 1
        else:
            unknown += 1

    snapshot = PriceSnapshot(fetched_at=fetched_at, models=models)
    # Round-trip validation prevents the updater from writing structures the runtime cannot read.
    snapshot = validate_snapshot(snapshot.to_json_dict())
    return snapshot, RefreshCounts(
        models_dev=models_dev,
        portkey=portkey,
        stale=stale,
        manual=len(manual_entries),
        unknown=unknown,
    )


def write_price_snapshot_atomic(snapshot: PriceSnapshot, path: str | Path) -> None:
    """Write a complete snapshot and atomically replace the destination."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            json.dump(snapshot.to_json_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise


async def fetch_json(client: httpx.AsyncClient, url: str, *, max_bytes: int) -> object:
    """Fetch one JSON document once while enforcing a hard response-size limit."""
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise PriceSnapshotError(f"Response exceeds {max_bytes} bytes")
            except ValueError as exc:
                raise PriceSnapshotError("Invalid Content-Length header") from exc
        chunks: list[bytes] = []
        received = 0
        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > max_bytes:
                raise PriceSnapshotError(f"Response exceeds {max_bytes} bytes")
            chunks.append(chunk)
    try:
        return json.loads(b"".join(chunks))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PriceSnapshotError(f"Pricing response is not valid JSON: {url}") from exc


async def refresh_prices(
    app_settings: Settings,
    *,
    client: httpx.AsyncClient,
    existing_path: str | Path = DEFAULT_PRICE_PATH,
    fetched_at: str | None = None,
) -> tuple[PriceSnapshot, RefreshCounts]:
    """Fetch and merge a complete replacement snapshot without writing it."""
    timestamp = fetched_at or utc_now_string()
    configured = resolve_configured_models(app_settings)
    models_dev_payload = await fetch_json(client, MODELS_DEV_URL, max_bytes=MODELS_DEV_MAX_BYTES)
    refreshed = normalize_models_dev(models_dev_payload, configured, fetched_at=timestamp)

    unresolved = {route for route in configured if route.key not in refreshed and source_provider_name(route.provider)}
    for provider in sorted({route.provider for route in unresolved}):
        source_provider = source_provider_name(provider)
        if source_provider is None:
            continue
        url = PORTKEY_URL_TEMPLATE.format(provider=source_provider)
        try:
            portkey_payload = await fetch_json(client, url, max_bytes=PORTKEY_MAX_BYTES)
            refreshed.update(normalize_portkey(portkey_payload, unresolved, provider=provider, fetched_at=timestamp))
        except (httpx.HTTPError, PriceSnapshotError) as exc:
            logger.warning("Portkey price refresh failed provider=%s error=%s", provider, type(exc).__name__)

    previous = load_price_snapshot(existing_path)
    return build_refreshed_snapshot(configured, refreshed, previous, fetched_at=timestamp)


async def refresh_price_snapshot(
    app_settings: Settings,
    *,
    path: str | Path = DEFAULT_PRICE_PATH,
    fetched_at: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> RefreshCounts:
    """Refresh and atomically install the local snapshot for CLI or startup use."""
    if client is not None:
        snapshot, counts = await refresh_prices(
            app_settings,
            client=client,
            existing_path=path,
            fetched_at=fetched_at,
        )
    else:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as owned_client:
            snapshot, counts = await refresh_prices(
                app_settings,
                client=owned_client,
                existing_path=path,
                fetched_at=fetched_at,
            )

    await asyncio.to_thread(write_price_snapshot_atomic, snapshot, path)
    return counts
