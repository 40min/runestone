"""Focused marker coverage for unexpected authentication failures."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from runestone.api.auth_endpoints import login, register
from runestone.api.schemas import LoginRequest, RegisterRequest
from runestone.auth.dependencies import get_current_user
from runestone.services.auth_service import AuthService


@pytest.mark.anyio
async def test_register_unexpected_failure_has_only_fixed_marker(caplog: pytest.LogCaptureFixture) -> None:
    service = AsyncMock(spec=AuthService)
    service.register_user.side_effect = RuntimeError("SENTINEL-email password=SENTINEL-password")

    with caplog.at_level(logging.ERROR, logger="runestone.api.auth_endpoints"):
        with pytest.raises(RuntimeError, match="SENTINEL-email"):
            await register(RegisterRequest(email="SENTINEL-email", password="SENTINEL-password"), service)

    assert caplog.records[-1].runestone_telemetry == {
        "operation": "auth_register",
        "outcome": "failed",
        "route_template": "/api/auth/register",
        "status_code": 500,
    }

    service.register_user.side_effect = ValueError("original registration failure")
    with patch("runestone.api.auth_endpoints.logger.error", side_effect=RuntimeError("logging failed")):
        with pytest.raises(ValueError, match="original registration failure"):
            await register(RegisterRequest(email="registered@example.com", password="password123"), service)


@pytest.mark.anyio
async def test_login_unexpected_failure_has_only_fixed_marker(caplog: pytest.LogCaptureFixture) -> None:
    service = AsyncMock(spec=AuthService)
    service.login.side_effect = RuntimeError("SENTINEL-email password=SENTINEL-password")

    with caplog.at_level(logging.ERROR, logger="runestone.api.auth_endpoints"):
        with pytest.raises(RuntimeError, match="SENTINEL-email"):
            await login(LoginRequest(email="SENTINEL-email", password="SENTINEL-password"), service)

    assert caplog.records[-1].runestone_telemetry == {
        "operation": "auth_login",
        "outcome": "failed",
        "route_template": "/api/auth/",
        "status_code": 500,
    }

    service.login.side_effect = ValueError("original login failure")
    with patch("runestone.api.auth_endpoints.logger.error", side_effect=RuntimeError("logging failed")):
        with pytest.raises(ValueError, match="original login failure"):
            await login(LoginRequest(email="login@example.com", password="password123"), service)


@pytest.mark.anyio
async def test_token_resolution_unexpected_failure_has_only_fixed_marker(caplog: pytest.LogCaptureFixture) -> None:
    service = AsyncMock(spec=AuthService)
    service.resolve_access_token.side_effect = RuntimeError("SENTINEL-jwt")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="SENTINEL-jwt")

    with caplog.at_level(logging.ERROR, logger="runestone.auth.dependencies"):
        with pytest.raises(RuntimeError, match="SENTINEL-jwt"):
            await get_current_user(credentials, service)

    assert caplog.records[-1].runestone_telemetry == {
        "operation": "auth_token_validation",
        "outcome": "failed",
        "status_code": 500,
    }

    service.resolve_access_token.side_effect = ValueError("original token failure")
    with patch("runestone.auth.dependencies.logger.error", side_effect=RuntimeError("logging failed")):
        with pytest.raises(ValueError, match="original token failure"):
            await get_current_user(credentials, service)
