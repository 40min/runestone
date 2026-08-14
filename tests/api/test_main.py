"""
Tests for the main FastAPI application.

This module tests the FastAPI app setup, configuration, and basic endpoints
like health checks.
"""

import asyncio
import logging
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

import runestone.api.main as main_module
import runestone.model_costs.startup as startup_module
from runestone.api.main import app
from runestone.model_costs.pricing import RefreshCounts


def patch_lifespan_dependencies(monkeypatch) -> None:
    """Replace unrelated startup collaborators with inert test doubles."""

    async def setup_database() -> None:
        return None

    monkeypatch.setattr(main_module, "setup_database", setup_database)
    monkeypatch.setattr(main_module, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr(main_module, "build_service_llm_model", lambda **kwargs: object())
    monkeypatch.setattr(main_module, "GrammarService", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "GrammarIndex", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "AgentsManager", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "TTSService", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "VoiceService", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "create_voice_synthesis_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "create_voice_transcription_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(main_module, "create_voice_enhancement_client", lambda *args, **kwargs: object())


class TestFastAPIApp:
    """Test cases for the FastAPI application setup."""

    async def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        assert app is not None
        assert app.title == "Runestone API"
        assert app.version == "1.0.0"

    async def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "runestone-api"

    async def test_cors_middleware(self):
        """Test that CORS middleware is properly configured."""
        # Check that CORS headers are present in responses
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health", headers={"Origin": "http://localhost:5173"})

            # Check CORS headers are present
            assert "access-control-allow-origin" in response.headers
            assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
            assert "access-control-allow-credentials" in response.headers

    async def test_api_router_included(self):
        """Test that the API router is properly included."""
        # The /api/health endpoint should exist, indicating router is included
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200


async def test_startup_price_refresh_succeeds_without_blocking_readiness(monkeypatch, caplog) -> None:
    patch_lifespan_dependencies(monkeypatch)
    started = asyncio.Event()
    release = asyncio.Event()

    async def refresh_price_snapshot(settings) -> RefreshCounts:
        started.set()
        await release.wait()
        return RefreshCounts(models_dev=3, portkey=2, stale=1, manual=1, unknown=0)

    monkeypatch.setattr(startup_module, "refresh_price_snapshot", refresh_price_snapshot)
    test_app = SimpleNamespace(state=SimpleNamespace())

    with caplog.at_level(logging.INFO):
        async with main_module.lifespan(test_app):  # type: ignore[arg-type]
            await started.wait()
            task = test_app.state.model_price_refresh_task
            assert task.get_name() == "model-price-refresh"
            assert task.done() is False
            release.set()
            await task

    assert "models.dev=3 portkey=2 stale=1 manual=1 unknown=0" in caplog.text


async def test_startup_price_refresh_failure_is_visible_and_non_fatal(monkeypatch, caplog) -> None:
    patch_lifespan_dependencies(monkeypatch)

    async def refresh_price_snapshot(settings) -> RefreshCounts:
        raise RuntimeError("feed unavailable")

    monkeypatch.setattr(startup_module, "refresh_price_snapshot", refresh_price_snapshot)
    test_app = SimpleNamespace(state=SimpleNamespace())

    with caplog.at_level(logging.ERROR):
        async with main_module.lifespan(test_app):  # type: ignore[arg-type]
            await test_app.state.model_price_refresh_task

    assert "Startup model price refresh failed" in caplog.text
    assert "feed unavailable" in caplog.text


async def test_shutdown_cancels_unfinished_price_refresh(monkeypatch) -> None:
    patch_lifespan_dependencies(monkeypatch)
    started = asyncio.Event()

    async def refresh_price_snapshot(settings) -> RefreshCounts:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(startup_module, "refresh_price_snapshot", refresh_price_snapshot)
    test_app = SimpleNamespace(state=SimpleNamespace())

    async with main_module.lifespan(test_app):  # type: ignore[arg-type]
        await started.wait()
        task = test_app.state.model_price_refresh_task

    assert task.cancelled() is True
