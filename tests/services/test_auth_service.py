"""Tests for authentication use cases and transaction ownership."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runestone.core.exceptions import (
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    RegistrationError,
    UserEmailAlreadyExistsError,
)
from runestone.db.models import User
from runestone.services.auth_service import AuthService


@pytest.fixture
def auth_repository():
    """Return an authentication-ready user repository double."""
    repository = Mock()
    repository.get_by_email = AsyncMock(return_value=None)
    repository.get_by_id = AsyncMock(return_value=None)
    repository.add_user = AsyncMock()
    repository.commit = AsyncMock()
    repository.rollback = AsyncMock()
    return repository


@pytest.fixture
def auth_service(auth_repository):
    """Build AuthService with explicit test settings."""
    settings = SimpleNamespace(min_password_length=6, jwt_expiration_days=7)
    return AuthService(auth_repository, settings)


async def test_register_user_requires_email_and_password(auth_service, auth_repository):
    with pytest.raises(RegistrationError, match="Email and password are required"):
        await auth_service.register_user(None, None)

    auth_repository.get_by_email.assert_not_awaited()
    auth_repository.rollback.assert_not_awaited()


async def test_register_user_rejects_short_password(auth_service, auth_repository):
    with pytest.raises(RegistrationError, match="Password must be at least 6 characters long"):
        await auth_service.register_user("new@example.com", "short")

    auth_repository.get_by_email.assert_not_awaited()
    auth_repository.rollback.assert_not_awaited()


@patch("runestone.services.auth_service.hash_password")
async def test_register_user_rejects_existing_email_before_add(hash_password, auth_service, auth_repository):
    auth_repository.get_by_email.return_value = User(id=1, email="new@example.com")

    with pytest.raises(UserEmailAlreadyExistsError, match="Email already registered"):
        await auth_service.register_user("new@example.com", "password")

    hash_password.assert_not_called()
    auth_repository.add_user.assert_not_awaited()
    auth_repository.commit.assert_not_awaited()
    auth_repository.rollback.assert_not_awaited()


@patch("runestone.services.auth_service.hash_password", return_value="hashed-password")
async def test_register_user_commits_once_and_returns_default_account(hash_password, auth_service, auth_repository):
    user = await auth_service.register_user("new@example.com", "password")

    assert user.email == "new@example.com"
    assert user.hashed_password == "hashed-password"
    assert user.name == "new"
    assert user.timezone == "UTC"
    assert user.pages_recognised_count == 0
    auth_repository.get_by_email.assert_awaited_once_with("new@example.com")
    hash_password.assert_called_once_with("password")
    auth_repository.add_user.assert_awaited_once_with(user)
    auth_repository.commit.assert_awaited_once_with()
    auth_repository.rollback.assert_not_awaited()


async def test_register_user_rolls_back_repository_duplicate_race(auth_service, auth_repository):
    auth_repository.add_user.side_effect = UserEmailAlreadyExistsError("Email already registered")

    with pytest.raises(UserEmailAlreadyExistsError, match="Email already registered"):
        await auth_service.register_user("new@example.com", "password")

    auth_repository.add_user.assert_awaited_once()
    auth_repository.commit.assert_not_awaited()
    auth_repository.rollback.assert_awaited_once_with()


async def test_register_user_rolls_back_unexpected_persistence_failure(auth_service, auth_repository):
    failure = RuntimeError("database unavailable")
    auth_repository.commit.side_effect = failure

    with pytest.raises(RuntimeError, match="database unavailable"):
        await auth_service.register_user("new@example.com", "password")

    auth_repository.rollback.assert_awaited_once_with()


@patch("runestone.services.auth_service.verify_password")
async def test_login_rejects_unknown_email_without_password_check(verify_password, auth_service, auth_repository):
    with pytest.raises(InvalidCredentialsError, match="Incorrect email or password"):
        await auth_service.login("missing@example.com", "password")

    verify_password.assert_not_called()


@patch("runestone.services.auth_service.verify_password", return_value=False)
async def test_login_rejects_wrong_password(verify_password, auth_service, auth_repository):
    auth_repository.get_by_email.return_value = User(
        id=1,
        email="user@example.com",
        hashed_password="stored-hash",
        name="User",
        active=True,
    )

    with pytest.raises(InvalidCredentialsError, match="Incorrect email or password"):
        await auth_service.login("user@example.com", "wrong")

    verify_password.assert_called_once_with("wrong", "stored-hash")


@patch("runestone.services.auth_service.verify_password", return_value=True)
async def test_login_rejects_inactive_user(_verify_password, auth_service, auth_repository):
    auth_repository.get_by_email.return_value = User(
        id=1,
        email="user@example.com",
        hashed_password="stored-hash",
        name="User",
        active=False,
    )

    with pytest.raises(InactiveUserError, match="User is not active"):
        await auth_service.login("user@example.com", "password")


@patch("runestone.services.auth_service.create_access_token", return_value="access-token")
@patch("runestone.services.auth_service.verify_password", return_value=True)
async def test_login_returns_access_token(verify_password, create_access_token, auth_service, auth_repository):
    user = User(
        id=42,
        email="user@example.com",
        hashed_password="stored-hash",
        name="User",
        active=True,
    )
    auth_repository.get_by_email.return_value = user

    token = await auth_service.login("user@example.com", "password")

    assert token == "access-token"
    verify_password.assert_called_once_with("password", "stored-hash")
    create_access_token.assert_called_once()
    assert create_access_token.call_args.kwargs["data"] == {"sub": "42"}
    assert create_access_token.call_args.kwargs["expires_delta"].days == 7


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "Invalid authentication credentials"),
        ({"exp": 1}, "Invalid token payload"),
        ({"sub": "not-an-id"}, "Invalid user ID in token"),
        ({"sub": ["1"]}, "Invalid user ID in token"),
    ],
)
async def test_resolve_access_token_rejects_invalid_payloads(payload, message, auth_service, auth_repository):
    with patch("runestone.services.auth_service.verify_token", return_value=payload):
        with pytest.raises(InvalidAccessTokenError, match=message):
            await auth_service.resolve_access_token("token")

    auth_repository.get_by_id.assert_not_awaited()


@patch("runestone.services.auth_service.verify_token", return_value={"sub": "42"})
async def test_resolve_access_token_rejects_missing_user(_verify_token, auth_service, auth_repository):
    with pytest.raises(InvalidAccessTokenError, match="User not found"):
        await auth_service.resolve_access_token("token")

    auth_repository.get_by_id.assert_awaited_once_with(42)


@patch("runestone.services.auth_service.verify_token", return_value={"sub": "42"})
async def test_resolve_access_token_rejects_inactive_user(_verify_token, auth_service, auth_repository):
    auth_repository.get_by_id.return_value = User(id=42, email="user@example.com", name="User", active=False)

    with pytest.raises(InactiveUserError, match="User is not active"):
        await auth_service.resolve_access_token("token")


@patch("runestone.services.auth_service.verify_token", return_value={"sub": "42"})
async def test_resolve_access_token_returns_active_user(_verify_token, auth_service, auth_repository):
    user = User(id=42, email="user@example.com", name="User", active=True)
    auth_repository.get_by_id.return_value = user

    assert await auth_service.resolve_access_token("token") is user
