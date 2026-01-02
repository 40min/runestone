"""
Tests for chat API endpoints.

This module tests the chat endpoints including authentication,
request validation, and response handling.
"""

from unittest.mock import MagicMock

import pytest

from runestone.dependencies import get_agent_service


def _create_user_and_login(client, email, password):
    """Helper function to create a user and get auth token."""
    # Register
    client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    # Login
    login_response = client.post(
        "/api/auth/",
        json={"email": email, "password": password},
    )
    return login_response.json()["access_token"]


@pytest.fixture
def mock_agent_service(client):
    """Fixture to provide a mock agent service and register it as a dependency override."""
    mock = MagicMock()
    mock.generate_response.return_value = "Mock response"
    client.app.dependency_overrides[get_agent_service] = lambda: mock
    yield mock
    client.app.dependency_overrides.clear()


def test_send_message_success(client, mock_agent_service):
    """Test successful message sending."""
    mock_agent_service.generate_response.return_value = "Hej! Jag mår bra, tack!"

    token = _create_user_and_login(client, "test@example.com", "testpass123")

    # Send a chat message
    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hej! Hur mår du?", "history": []},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert "message" in data
    assert data["message"] == "Hej! Jag mår bra, tack!"
    mock_agent_service.generate_response.assert_called_once()


def test_send_message_with_history(client, mock_agent_service):
    """Test sending a message with conversation history."""
    mock_agent_service.generate_response.return_value = "Your name is Alice!"

    token = _create_user_and_login(client, "test2@example.com", "testpass123")

    # Send message with history
    history = [
        {"role": "user", "content": "My name is Alice"},
        {"role": "assistant", "content": "Nice to meet you, Alice!"},
    ]

    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What is my name?", "history": history},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert data["message"] == "Your name is Alice!"

    # Verify service was called with correct history
    call_args = mock_agent_service.generate_response.call_args
    assert call_args[0][0] == "What is my name?"
    assert len(call_args[0][1]) == 2


def test_send_message_requires_authentication(client, mock_agent_service):
    """Test that chat endpoint requires authentication."""
    # The 'client' fixture in conftest.py overrides get_current_user by default.
    # To test authentication, we need to remove that override or provide one that fails.
    from runestone.auth.dependencies import get_current_user

    # Force authentication failure by removing the override and not providing a token
    # or by overriding to raise 401.
    client.app.dependency_overrides[get_current_user] = None
    if get_current_user in client.app.dependency_overrides:
        del client.app.dependency_overrides[get_current_user]

    try:
        response = client.post("/api/chat/message", json={"message": "Hello", "history": []})
        # If the override was successfully removed, it should fail with 403 (from HTTPBearer)
        # or 401 if it reached our get_current_user logic without a token.
        assert response.status_code in (401, 403)
    finally:
        # Restore the behavior expected by other tests if needed,
        # though yield cleans up usually.
        client.app.dependency_overrides.clear()


def test_send_message_empty_message(client):
    """Test that empty messages are rejected."""
    token = _create_user_and_login(client, "test3@example.com", "testpass123")

    # Try to send empty message
    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "", "history": []},
    )

    assert chat_response.status_code == 422  # Validation error


def test_send_message_invalid_payload(client):
    """Test that invalid payloads are rejected."""
    token = _create_user_and_login(client, "test4@example.com", "testpass123")

    # Send invalid payload (missing message field)
    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"history": []},
    )

    assert chat_response.status_code == 422


def test_send_message_service_error(client, mock_agent_service):
    """Test error handling when agent service fails."""
    mock_agent_service.generate_response.side_effect = Exception("LLM API Error")

    token = _create_user_and_login(client, "test5@example.com", "testpass123")

    # Send message
    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hello", "history": []},
    )

    assert chat_response.status_code == 500
    assert "Failed to generate response" in chat_response.json()["detail"]


def test_send_message_invalid_history_format(client):
    """Test that invalid history format is rejected."""
    token = _create_user_and_login(client, "test6@example.com", "testpass123")

    # Send message with invalid history (missing 'role' field)
    invalid_history = [{"content": "Invalid message"}]

    chat_response = client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hello", "history": invalid_history},
    )

    assert chat_response.status_code == 422
