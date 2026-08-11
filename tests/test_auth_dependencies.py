"""Tests for FastAPI authentication dependency error mapping."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from runestone.auth.dependencies import get_current_user
from runestone.core.exceptions import InactiveUserError, InvalidAccessTokenError
from runestone.db.models import User


def bearer_token() -> HTTPAuthorizationCredentials:
    """Return a representative bearer credential."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")


async def test_get_current_user_delegates_token_resolution():
    user = User(id=1, email="user@example.com", name="User", active=True)
    service = Mock()
    service.resolve_access_token = AsyncMock(return_value=user)

    assert await get_current_user(bearer_token(), service) is user
    service.resolve_access_token.assert_awaited_once_with("token")


async def test_get_current_user_maps_invalid_token_to_unauthorized():
    service = Mock()
    service.resolve_access_token = AsyncMock(side_effect=InvalidAccessTokenError("Invalid token payload"))

    with pytest.raises(HTTPException) as raised:
        await get_current_user(bearer_token(), service)

    assert raised.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert raised.value.detail == "Invalid token payload"
    assert raised.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_get_current_user_maps_inactive_user_to_forbidden():
    service = Mock()
    service.resolve_access_token = AsyncMock(side_effect=InactiveUserError("User is not active"))

    with pytest.raises(HTTPException) as raised:
        await get_current_user(bearer_token(), service)

    assert raised.value.status_code == status.HTTP_403_FORBIDDEN
    assert raised.value.detail == "User is not active"
    assert raised.value.headers is None
