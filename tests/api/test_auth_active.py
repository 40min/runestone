"""
Integration tests for the user active flag in authorization.
"""

from fastapi import status

from runestone.auth.security import hash_password


class TestAuthActiveFlag:
    """Test cases for the user active flag in authorization."""

    async def test_active_user_can_access_me(self, client):
        """Test that an active user can access their profile."""
        # By default our client fixture has an active user (active=True)
        response = await client.get("/api/me")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == client.user.email

    async def test_inactive_user_cannot_access_me(self, client_with_overrides, user_factory):
        """Test that an inactive user is forbidden from accessing their profile."""
        # Create an inactive user
        inactive_user = await user_factory(active=False)

        # Create a client with this inactive user
        async for client, _ in client_with_overrides(current_user=inactive_user):
            response = await client.get("/api/me")

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert response.json()["detail"] == "User is not active"

    async def test_inactive_user_cannot_access_vocabulary(self, client_with_overrides, user_factory):
        """Test that an inactive user is forbidden from accessing vocabulary."""
        inactive_user = await user_factory(active=False)

        async for client, _ in client_with_overrides(current_user=inactive_user):
            response = await client.get("/api/vocabulary")

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert response.json()["detail"] == "User is not active"

    async def test_inactive_user_cannot_login(self, client_with_overrides, user_factory):
        """Test that an inactive user cannot log in."""

        # Create an inactive user
        email = "inactive@example.com"
        password = "password123"
        await user_factory(email=email, hashed_password=hash_password(password), active=False)

        # Attempt to login
        async for client, _ in client_with_overrides():
            response = await client.post("/api/auth/", json={"email": email, "password": password})

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["detail"] == "User is not active"
