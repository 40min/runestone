"""
Tests for chat API endpoints.

This module tests the chat endpoints including authentication,
request validation, and response handling.
"""


def test_send_message_success(client_with_mock_agent_service, db_session):
    """Test successful message sending."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = (
        "Hej! Jag mår bra, tack!",
        [{"title": "Nyhet", "url": "https://example.com/news", "date": "2026-02-05"}],
    )

    # Send a chat message - history is now managed by the backend
    chat_response = client.post(
        "/api/chat/message",
        json={"message": "Hej! Hur mår du?"},
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert "message" in data
    assert data["message"] == "Hej! Jag mår bra, tack!"
    assert data["sources"] == [{"title": "Nyhet", "url": "https://example.com/news", "date": "2026-02-05"}]
    mock_agent_service.generate_response.assert_called_once()


def test_history_includes_sources(client_with_mock_agent_service, db_session):
    """Test that chat history returns sources for assistant messages."""
    client, mock_agent_service = client_with_mock_agent_service
    mock_agent_service.generate_response.return_value = (
        "Svar med källor",
        [{"title": "Nyhet", "url": "https://example.com/news", "date": "2026-02-05"}],
    )

    client.post("/api/chat/message", json={"message": "Hej!"})

    response = client.get("/api/chat/history")
    assert response.status_code == 200
    data = response.json()
    assistant_messages = [msg for msg in data["messages"] if msg["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["sources"] == [
        {"title": "Nyhet", "url": "https://example.com/news", "date": "2026-02-05"}
    ]


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
        "Here's the translated text: Hej (Hello). Hur mår du? (How are you?)",
        None,
    )

    # Mock the processor dependency
    mock_processor = Mock()
    # Create a proper OCRResult-like object
    mock_ocr_result = Mock()
    mock_ocr_result.transcribed_text = "Hej. Hur mår du?"
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
    # mock_processor.run_ocr is called inside ChatService now, but since we mock
    # the processor injected into ChatService, this assertion still holds.
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
    mock_ocr_result.transcribed_text = ""
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


def test_send_image_file_too_large(client_with_mock_agent_service):
    """Test that files larger than configured limit are rejected."""
    import io

    from runestone.config import settings

    client, _ = client_with_mock_agent_service

    # Create a file larger than max size
    large_file_size = (settings.chat_image_max_size_mb + 1) * 1024 * 1024
    large_image_data = io.BytesIO(b"x" * large_file_size)
    files = {"file": ("large.jpg", large_image_data, "image/jpeg")}

    response = client.post("/api/chat/image", files=files)

    assert response.status_code == 400
    assert f"File too large. Maximum size is {settings.chat_image_max_size_mb}MB." in response.json()["detail"]


def test_send_image_missing_file(client_with_mock_agent_service):
    """Test that request without file parameter is rejected."""
    client, _ = client_with_mock_agent_service

    # Send request without files parameter
    response = client.post("/api/chat/image")

    assert response.status_code == 422  # Validation error


def test_send_image_whitespace_only_ocr(client_with_mock_agent_service, monkeypatch):
    """Test image upload when OCR returns only whitespace."""
    import io
    from unittest.mock import Mock

    client, _ = client_with_mock_agent_service

    # Mock the processor dependency
    mock_processor = Mock()
    # Create OCR result with whitespace-only text
    mock_ocr_result = Mock()
    mock_ocr_result.transcribed_text = "   \n\t  \n  "
    mock_ocr_result.character_count = 10
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
