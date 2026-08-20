import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from runestone.model_costs import pricing
from runestone.model_costs.pricing import (
    ConfiguredModel,
    ModelPrice,
    PriceSnapshot,
    PriceSnapshotError,
    RefreshCounts,
    build_refreshed_snapshot,
    fetch_json,
    load_price_snapshot,
    normalize_models_dev,
    normalize_portkey,
    refresh_price_snapshot,
    refresh_prices,
    resolve_configured_models,
    validate_snapshot,
    write_price_snapshot_atomic,
)

FIXTURES = Path(__file__).parent / "fixtures"
FETCHED_AT = "2026-08-11T12:00:00Z"


def read_fixture(name: str) -> object:
    with (FIXTURES / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def model_price(source: str = "models.dev", *, stale: bool = False) -> ModelPrice:
    return ModelPrice(
        source=source,
        source_url=None if source == "manual" else "https://example.test/prices",
        source_model_id="gpt-4o-mini",
        last_successful_at=FETCHED_AT,
        stale=stale,
        rates_usd={"input_token": Decimal("0.00000015")},
    )


def test_models_dev_normalizes_usd_per_million_for_all_provider_routes() -> None:
    configured = {
        ConfiguredModel("openai", "gpt-4o-mini"),
        ConfiguredModel("gemini", "gemini-2.5-flash"),
        ConfiguredModel("openrouter", "openai/gpt-4o-mini"),
    }

    result = normalize_models_dev(read_fixture("models_dev_api.json"), configured, fetched_at=FETCHED_AT)

    assert result["openai/gpt-4o-mini"].rates_usd == {
        "input_token": Decimal("0.00000015"),
        "output_token": Decimal("0.00000060"),
        "cached_input_token": Decimal("0.000000075"),
    }
    assert result["gemini/gemini-2.5-flash"].rates_usd["output_token"] == Decimal("0.00000250")
    assert result["openrouter/openai/gpt-4o-mini"].rates_usd["input_token"] == Decimal("0.00000020")


@pytest.mark.parametrize(
    ("fixture", "provider", "model", "expected_input"),
    [
        ("portkey_openai_pricing.json", "openai", "gpt-4o-mini", Decimal("0.00000015")),
        ("portkey_google_pricing.json", "gemini", "gemini-2.5-flash", Decimal("0.00000030")),
        (
            "portkey_openrouter_pricing.json",
            "openrouter",
            "openai/gpt-4o-mini",
            Decimal("0.00000020"),
        ),
    ],
)
def test_portkey_normalizes_cents_per_token(fixture: str, provider: str, model: str, expected_input: Decimal) -> None:
    route = ConfiguredModel(provider, model)

    result = normalize_portkey(read_fixture(fixture), {route}, provider=provider, fetched_at=FETCHED_AT)

    assert result[route.key].rates_usd["input_token"] == expected_input
    assert result[route.key].source == "portkey"


def test_models_dev_rejects_incompatible_provider_shape() -> None:
    configured = {ConfiguredModel("openai", "gpt-4o-mini")}

    with pytest.raises(PriceSnapshotError):
        normalize_models_dev({"unexpected": {}}, configured, fetched_at=FETCHED_AT)


def test_refresh_preserves_manual_and_marks_previous_unresolved_stale() -> None:
    previous = PriceSnapshot(
        fetched_at="2026-08-10T12:00:00Z",
        models={
            "elevenlabs/eleven_multilingual_v2": model_price("manual"),
            "openai/old-model": model_price(),
        },
    )
    configured = {
        ConfiguredModel("elevenlabs", "eleven_multilingual_v2"),
        ConfiguredModel("openai", "old-model"),
        ConfiguredModel("gemini", "missing-model"),
    }

    snapshot, counts = build_refreshed_snapshot(configured, {}, previous, fetched_at=FETCHED_AT)

    assert snapshot.models["elevenlabs/eleven_multilingual_v2"].source == "manual"
    assert snapshot.models["openai/old-model"].stale is True
    assert counts.manual == 1
    assert counts.stale == 1
    assert counts.unknown == 1


def test_refresh_counts_distinguish_primary_and_fallback_sources() -> None:
    configured = {
        ConfiguredModel("openai", "primary-model"),
        ConfiguredModel("gemini", "fallback-model"),
    }
    refreshed = {
        "openai/primary-model": model_price("models.dev"),
        "gemini/fallback-model": model_price("portkey"),
    }

    _, counts = build_refreshed_snapshot(configured, refreshed, None, fetched_at=FETCHED_AT)

    assert counts.models_dev == 1
    assert counts.portkey == 1
    assert counts.models_dev + counts.portkey == 2


def test_atomic_writer_failure_leaves_existing_file_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "model_prices.json"
    target.write_text("last-valid", encoding="utf-8")
    snapshot = PriceSnapshot(fetched_at=FETCHED_AT, models={"openai/gpt-4o-mini": model_price()})

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("replace blocked")

    monkeypatch.setattr(pricing.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace blocked"):
        write_price_snapshot_atomic(snapshot, target)

    assert target.read_text(encoding="utf-8") == "last-valid"
    assert list(tmp_path.glob("*.tmp")) == []


def test_local_lookup_warns_for_stale_and_never_fetches_or_imports_database(
    tmp_path: Path,
    caplog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "model_prices.json"
    snapshot = PriceSnapshot(
        fetched_at=FETCHED_AT,
        models={"openai/gpt-4o-mini": model_price(stale=True)},
    )
    write_price_snapshot_atomic(snapshot, target)

    async def fail_fetch(*args: object, **kwargs: object) -> object:
        raise AssertionError("local lookup must not fetch prices")

    monkeypatch.setattr(pricing, "fetch_json", fail_fetch)
    loaded = load_price_snapshot(target)

    assert loaded is not None
    assert loaded.models["openai/gpt-4o-mini"].rates_usd["input_token"] == Decimal("0.00000015")
    assert "stale entries" in caplog.text
    source = Path(pricing.__file__).read_text(encoding="utf-8")
    assert "runestone.db" not in source
    assert "sqlalchemy" not in source.lower()


@pytest.mark.parametrize("raw_rate", [0.00000015, 1, Decimal("0.00000015"), True, None])
def test_snapshot_validation_rejects_non_string_money(raw_rate: object) -> None:
    payload = PriceSnapshot(fetched_at=FETCHED_AT, models={"openai/gpt-4o-mini": model_price()}).to_json_dict()
    models = payload["models"]
    assert isinstance(models, dict)
    entry = models["openai/gpt-4o-mini"]
    assert isinstance(entry, dict)
    rates = entry["rates_usd"]
    assert isinstance(rates, dict)
    rates["input_token"] = raw_rate

    with pytest.raises(PriceSnapshotError, match="must be a decimal string"):
        validate_snapshot(payload)


def test_snapshot_validation_rejects_invalid_schema() -> None:
    payload = PriceSnapshot(fetched_at=FETCHED_AT, models={"openai/gpt-4o-mini": model_price()}).to_json_dict()
    payload["schema_version"] = 2

    with pytest.raises(PriceSnapshotError):
        validate_snapshot(payload)


class FakeSettings:
    teacher_backup_model = "backup"
    voice_transcription_provider = "openai"
    voice_transcription_model = "whisper-1"
    voice_enhancement_model = "gpt-4o-mini"
    tts_provider = "elevenlabs"
    tts_model = "unused"
    elevenlabs_tts_model = "eleven_multilingual_v2"

    def get_agent_llm_settings(self, name: str) -> object:
        provider = "gemini" if name in {"teacher_backup", "memory_maintainer"} else "openrouter"
        return SimpleNamespace(provider=provider, model=f"{name}-model")

    def resolve_service_llm_provider(self) -> str:
        return "openai"

    def resolve_service_llm_model(self, provider: str) -> str:
        return "service-model"

    def resolve_ocr_llm_provider(self) -> str:
        return "gemini"

    def resolve_ocr_llm_model(self) -> str:
        return "ocr-model"


def test_configured_model_resolver_covers_agents_services_and_voice() -> None:
    configured = resolve_configured_models(FakeSettings())  # type: ignore[arg-type]

    assert ConfiguredModel("openrouter", "teacher-model") in configured
    assert ConfiguredModel("gemini", "teacher_backup-model") in configured
    assert ConfiguredModel("openai", "service-model") in configured
    assert ConfiguredModel("gemini", "ocr-model") in configured
    assert ConfiguredModel("openai", "whisper-1") in configured
    assert ConfiguredModel("openai", "gpt-4o-mini") in configured
    assert ConfiguredModel("elevenlabs", "eleven_multilingual_v2") in configured


class AsyncResponse:
    def __init__(
        self, payload: object, *, headers: dict[str, str] | None = None, chunks: list[bytes] | None = None
    ) -> None:
        self.payload = payload
        self.headers = headers or {}
        self.chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        if self.chunks is not None:
            for chunk in self.chunks:
                yield chunk
            return
        yield json.dumps(self.payload).encode()


class SingleResponseClient:
    def __init__(self, response: AsyncResponse) -> None:
        self.response = response

    def stream(self, method: str, url: str) -> AsyncResponse:
        assert method == "GET"
        assert url == "https://example.test/prices"
        return self.response


class FixtureClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def stream(self, method: str, url: str) -> AsyncResponse:
        assert method == "GET"
        self.urls.append(url)
        if url == pricing.MODELS_DEV_URL:
            return AsyncResponse(read_fixture("models_dev_api.json"))
        provider = url.removesuffix(".json").rsplit("/", 1)[-1]
        return AsyncResponse(read_fixture(f"portkey_{provider}_pricing.json"))


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (AsyncResponse(None, headers={"content-length": "11"}), "Response exceeds 10 bytes"),
        (AsyncResponse(None, headers={"content-length": "invalid"}), "Invalid Content-Length header"),
        (AsyncResponse(None, chunks=[b"12345678901"]), "Response exceeds 10 bytes"),
        (AsyncResponse(None, chunks=[b"not-json"]), "Pricing response is not valid JSON"),
    ],
)
async def test_fetch_json_rejects_oversized_or_malformed_responses(
    response: AsyncResponse,
    expected_error: str,
) -> None:
    with pytest.raises(PriceSnapshotError, match=expected_error):
        await fetch_json(
            SingleResponseClient(response), "https://example.test/prices", max_bytes=10
        )  # type: ignore[arg-type]


async def test_updater_fetches_fixtures_without_live_network() -> None:
    script_path = Path(__file__).parents[2] / "scripts" / "update-model-prices.py"
    spec = importlib.util.spec_from_file_location("update_model_prices", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    client = FixtureClient()
    snapshot, counts = await module.refresh_prices(
        FakeSettings(),
        client=client,
        existing_path=FIXTURES / "does-not-exist.json",
        fetched_at=FETCHED_AT,
    )

    assert snapshot.schema_version == 1
    assert counts.models_dev + counts.portkey >= 1
    assert client.urls.count(pricing.MODELS_DEV_URL) == 1
    assert all(client.urls.count(url) == 1 for url in set(client.urls))


async def test_portkey_failure_preserves_primary_refresh_and_stale_previous_entry(tmp_path: Path) -> None:
    target = tmp_path / "model_prices.json"
    previous = PriceSnapshot(
        fetched_at="2026-08-10T12:00:00Z",
        models={"openai/whisper-1": model_price()},
    )
    write_price_snapshot_atomic(previous, target)

    class FailingPortkeyClient(FixtureClient):
        def stream(self, method: str, url: str) -> AsyncResponse:
            if url != pricing.MODELS_DEV_URL:
                raise httpx.ConnectError("portkey unavailable")
            return super().stream(method, url)

    snapshot, counts = await refresh_prices(
        FakeSettings(),  # type: ignore[arg-type]
        client=FailingPortkeyClient(),  # type: ignore[arg-type]
        existing_path=target,
        fetched_at=FETCHED_AT,
    )

    assert snapshot.models["openai/gpt-4o-mini"].source == "models.dev"
    assert snapshot.models["openai/whisper-1"].stale is True
    assert counts.models_dev >= 1
    assert counts.portkey == 0
    assert counts.stale == 1


async def test_first_refresh_atomically_creates_complete_snapshot_and_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "new-state" / "model_prices.json"
    real_replace = pricing.os.replace
    replaced = False

    def inspect_replace(source: str, destination: Path) -> None:
        nonlocal replaced
        assert Path(destination) == target
        assert not target.exists()
        with Path(source).open(encoding="utf-8") as stream:
            validate_snapshot(json.load(stream))
        replaced = True
        real_replace(source, destination)

    monkeypatch.setattr(pricing.os, "replace", inspect_replace)

    counts = await refresh_price_snapshot(
        FakeSettings(),  # type: ignore[arg-type]
        path=target,
        client=FixtureClient(),  # type: ignore[arg-type]
        fetched_at=FETCHED_AT,
    )

    assert replaced is True
    assert target.parent.is_dir()
    assert load_price_snapshot(target) is not None
    assert counts.models_dev + counts.portkey >= 1


def test_updater_output_distinguishes_primary_and_fallback(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script_path = Path(__file__).parents[2] / "scripts" / "update-model-prices.py"
    spec = importlib.util.spec_from_file_location("update_model_prices_output", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    snapshot = PriceSnapshot(fetched_at=FETCHED_AT, models={})
    counts = RefreshCounts(models_dev=3, portkey=2, stale=1, manual=1, unknown=4)

    def fake_run(coroutine):
        coroutine.close()
        return snapshot, counts

    monkeypatch.setattr(module.asyncio, "run", fake_run)

    assert module.main(["--check"]) == 0
    assert capsys.readouterr().out.strip() == "models.dev=3 portkey=2 stale=1 manual=1 unknown=4"
