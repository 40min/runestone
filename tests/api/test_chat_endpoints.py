"""
Tests for chat API endpoints.

This module tests the chat endpoints including authentication,
request validation, and response handling.
"""


def test_send_message_success(client_with_mock_agent_service):
    """Test successful message sending."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = "Hej! Jag mår bra, tack!"

    # Send a chat message - authentication is handled by the fixture
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hej! Hur mår du?", "history": []},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert "message" in data
    assert data["message"] == "Hej! Jag mår bra, tack!"
    mock_agent_service.generate_response.assert_called_once()


def test_send_message_with_history(client_with_mock_agent_service):
    """Test sending a message with conversation history."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = "Your name is Alice!"

    # Send message with history
    history = [
        {"role": "user", "content": "My name is Alice"},
        {"role": "assistant", "content": "Nice to meet you, Alice!"},
    ]

    chat_response = client.post(
        "/api/chat/message",
        json={"message": "What is my name?", "history": history},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert data["message"] == "Your name is Alice!"

    # Verify service was called with correct history
    call_args = mock_agent_service.generate_response.call_args
    assert call_args[0][0] == "What is my name?"
    assert len(call_args[0][1]) == 2


def test_send_message_requires_authentication(client_with_mock_agent_service):
    """Test that chat endpoint requires authentication."""
    client, _ = client_with_mock_agent_service
    # The 'client' fixture in conftest.py overrides get_current_user by default.
    # To test authentication, we need to remove that override or provide one that fails.
    from runestone.auth.dependencies import get_current_user

    # Force authentication failure by removing the override
    if get_current_user in client.app.dependency_overrides:
        del client.app.dependency_overrides[get_current_user]

    response = client.post("/api/chat/message", json={"message": "Hello", "history": []})
    # Validation error 403 or 401 depending on how the dependency is structured
    assert response.status_code in (401, 403)


def test_send_message_empty_message(client):
    """Test that empty messages are rejected."""
    # Try to send empty message
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "", "history": []},
    )

    assert chat_response.status_code == 422  # Validation error


def test_send_message_invalid_payload(client):
    """Test that invalid payloads are rejected."""
    # Send invalid payload (missing message field)
    chat_response = client.post(
        "/api/chat/message",
        json={"history": []},
    )

    assert chat_response.status_code == 422


def test_send_message_service_error(client_with_mock_agent_service):
    """Test error handling when agent service fails."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.side_effect = Exception("LLM API Error")

    # Send message
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hello", "history": []},
    )

    assert chat_response.status_code == 500
    assert "Failed to generate response" in chat_response.json()["detail"]


def test_send_message_invalid_history_format(client):
    """Test that invalid history format is rejected."""
    # Send message with invalid history (missing 'role' field)
    invalid_history = [{"content": "Invalid message"}]

    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hello", "history": invalid_history},
    )

    assert chat_response.status_code == 422
