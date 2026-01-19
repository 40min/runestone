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


def test_send_message_service_error(client_with_mock_agent_service, db_session):
    """Test error handling when agent service fails."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.side_effect = Exception("LLM API Error")

    # Send message
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hello"},
    )

    assert chat_response.status_code == 500
    assert "Failed to generate response" in chat_response.json()["detail"]


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


def test_send_image_success(client_with_mock_agent_service, db_session, monkeypatch):
    """Test successful image upload with OCR and translation."""
    import io
    from unittest.mock import Mock

    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = (
        "Here's the translated text: Hej (Hello). Hur mår du? (How are you?)"
    )

    # Mock the processor dependency
    mock_processor = Mock()
    # Create a proper OCRResult-like object
    mock_ocr_result = Mock()
    mock_ocr_result.text = "Hej. Hur mår du?"
    mock_ocr_result.character_count = 16
    mock_processor.run_ocr.return_value = mock_ocr_result

    from runestone.dependencies import get_runestone_processor

    def override_processor():
        return mock_processor

    client.app.dependency_overrides[get_runestone_processor] = override_processor

    # Create a fake image file
    image_data = io.BytesIO(b"fake image content")
    files = {"file": ("test.jpg", image_data, "image/jpeg")}

    response = client.post("/api/chat/image", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "translated text" in data["message"].lower()
    mock_processor.run_ocr.assert_called_once()
    mock_agent_service.generate_response.assert_called_once()


def test_send_image_ocr_failure(client, monkeypatch):
    """Test image upload when OCR returns empty text."""
    import io
    from unittest.mock import Mock

    # Mock the processor dependency
    mock_processor = Mock()
    # Create a proper OCRResult-like object with empty text
    mock_ocr_result = Mock()
    mock_ocr_result.text = ""
    mock_ocr_result.character_count = 0
    mock_processor.run_ocr.return_value = mock_ocr_result

    from runestone.dependencies import get_runestone_processor

    def override_processor():
        return mock_processor

    client.app.dependency_overrides[get_runestone_processor] = override_processor

    # Create a fake image file
    image_data = io.BytesIO(b"fake image content")
    files = {"file": ("test.jpg", image_data, "image/jpeg")}

    response = client.post("/api/chat/image", files=files)

    assert response.status_code == 400
    assert "Could not recognize text from image" in response.json()["detail"]


def test_send_image_invalid_file_type(client):
    """Test image upload with invalid file type."""
    import io

    # Create a fake non-image file
    file_data = io.BytesIO(b"not an image")
    files = {"file": ("test.txt", file_data, "text/plain")}

    response = client.post("/api/chat/image", files=files)

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_send_image_requires_authentication(client):
    """Test that image endpoint requires authentication."""
    import io

    from runestone.auth.dependencies import get_current_user

    if get_current_user in client.app.dependency_overrides:
        del client.app.dependency_overrides[get_current_user]

    image_data = io.BytesIO(b"fake image content")
    files = {"file": ("test.jpg", image_data, "image/jpeg")}

    response = client.post("/api/chat/image", files=files)
    assert response.status_code in (401, 403)
