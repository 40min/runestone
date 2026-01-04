"""
Tests for chat API endpoints.

This module tests the chat endpoints including authentication,
request validation, and response handling.
"""


def test_send_message_success(client_with_mock_agent_service, db_session):
    """Test successful message sending."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = "Hej! Jag mår bra, tack!"

    # Send a chat message - history is now managed by the backend
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hej! Hur mår du?"},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert "message" in data
    assert data["message"] == "Hej! Jag mår bra, tack!"
    mock_agent_service.generate_response.assert_called_once()


def test_get_history_empty(client):
    """Test fetching empty chat history."""
    response = client.get("/api/chat/history")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 0


def test_clear_history(client):
    """Test clearing chat history."""
    # First send a message to create some history (mocked)
    client.post("/api/chat/message", json={"message": "Hello"})

    # Clear history
    response = client.delete("/api/chat/history")
    assert response.status_code == 204

    # Verify history is empty
    response = client.get("/api/chat/history")
    assert response.json()["messages"] == []


def test_send_message_requires_authentication(client):
    """Test that chat endpoint requires authentication."""
    # The 'client' fixture in conftest.py overrides get_current_user by default.
    # To test authentication, we need to remove that override.
    from runestone.auth.dependencies import get_current_user

    if get_current_user in client.app.dependency_overrides:
        del client.app.dependency_overrides[get_current_user]

    response = client.post("/api/chat/message", json={"message": "Hello"})
    assert response.status_code in (401, 403)


def test_send_message_empty_message(client):
    """Test that empty messages are rejected."""
    chat_response = client.post(
        "/api/chat/message",
        json={"message": ""},
    )
    assert chat_response.status_code == 422


def test_send_message_invalid_payload(client):
    """Test that invalid payloads are rejected."""
    chat_response = client.post(
        "/api/chat/message",
        json={"invalid": "field"},
    )
    assert chat_response.status_code == 422
