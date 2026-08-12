"""Integration coverage for registration and login contracts."""

from fastapi import status
from sqlalchemy import select

from runestone.auth.dependencies import get_current_user
from runestone.auth.security import hash_password
from runestone.db.models import User


async def test_register_persists_inactive_user_with_existing_response_contract(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": "registered@example.com", "password": "password123"},
    )

    assert response.status_code == status.HTTP_200_OK
    result = await client.db.execute(select(User).where(User.email == "registered@example.com"))
    user = result.scalar_one()
    assert response.json() == {"message": "User registered successfully", "user_id": user.id}
    assert user.name == "registered"
    assert user.active is False


async def test_register_preserves_required_fields_error(client):
    response = await client.post("/api/auth/register", json={})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email and password are required"


async def test_register_preserves_short_password_error(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": "registered@example.com", "password": "short"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Password must be at least 6 characters long"


async def test_register_preserves_duplicate_email_error(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": client.user.email, "password": "password123"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email already registered"


async def test_login_returns_token_that_resolves_current_user(client_with_overrides, user_factory):
    email = "login@example.com"
    password = "password123"
    user = await user_factory(email=email, hashed_password=hash_password(password), active=True)

    async for client, _ in client_with_overrides():
        login_response = await client.post("/api/auth/", json={"email": email, "password": password})

        assert login_response.status_code == status.HTTP_200_OK
        assert login_response.json()["token_type"] == "bearer"
        token = login_response.json()["access_token"]

        client.app.dependency_overrides.pop(get_current_user)
        profile_response = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.json()["id"] == user.id


async def test_login_preserves_incorrect_credentials_error(client):
    response = await client.post(
        "/api/auth/",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_login_rejects_inactive_user_with_authentication_challenge(client, user_factory):
    password = "password123"
    await user_factory(
        email="inactive-login@example.com",
        hashed_password=hash_password(password),
        active=False,
    )

    response = await client.post(
        "/api/auth/",
        json={"email": "inactive-login@example.com", "password": password},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "User is not active"
    assert response.headers["www-authenticate"] == "Bearer"
