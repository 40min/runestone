from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runestone.api.main import app
from runestone.api.schemas import VocabularyImproveRequest, VocabularyImproveResponse
from runestone.dependencies import get_vocabulary_service


@pytest.fixture
def client_with_mock_service():
    """Create a test client with mocked vocabulary service."""
    # Create mock service
    mock_service = Mock()

    # Override the dependency
    def override_get_vocabulary_service():
        return mock_service

    app.dependency_overrides[get_vocabulary_service] = override_get_vocabulary_service
    client = TestClient(app)

    yield client, mock_service

    # Clean up
    app.dependency_overrides.clear()


def test_improve_vocabulary_success(client_with_mock_service):
    """Test successful vocabulary improvement endpoint."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(translation="an apple", example_phrase="Jag äter ett äpple varje dag.")
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "include_translation": True}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] == "an apple"
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.include_translation is True


def test_improve_vocabulary_without_translation(client_with_mock_service):
    """Test vocabulary improvement endpoint without translation."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(translation=None, example_phrase="Jag äter ett äpple varje dag.")
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "include_translation": False}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."


def test_improve_vocabulary_service_error(client_with_mock_service):
    """Test vocabulary improvement endpoint with service error."""
    client, mock_service = client_with_mock_service

    # Mock service to raise exception
    mock_service.improve_item.side_effect = Exception("LLM service error")

    # Test request
    request_data = {"word_phrase": "ett äpple", "include_translation": True}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify error response
    assert response.status_code == 500
    response_data = response.json()
    assert "detail" in response_data
    assert response_data["detail"] == "An internal error occurred while improving vocabulary."


def test_improve_vocabulary_invalid_request(client_with_mock_service):
    """Test vocabulary improvement endpoint with invalid request."""
    client, mock_service = client_with_mock_service

    # Test with missing required field
    request_data = {
        "include_translation": True
        # Missing word_phrase
    }

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify validation error
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data


def test_improve_vocabulary_empty_response(client_with_mock_service):
    """Test vocabulary improvement endpoint with empty response."""
    client, mock_service = client_with_mock_service

    # Mock service response with empty fields
    mock_response = VocabularyImproveResponse(translation=None, example_phrase="")
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "include_translation": True}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == ""


def test_improve_vocabulary_with_extra_info(client_with_mock_service):
    """Test vocabulary improvement endpoint with extra_info."""
    client, mock_service = client_with_mock_service

    # Mock service response with extra_info
    mock_response = VocabularyImproveResponse(
        translation="an apple",
        example_phrase="Jag äter ett äpple varje dag.",
        extra_info="en-word, noun, base form: äpple",
    )
    mock_service.improve_item.return_value = mock_response

    # Test request with extra_info
    request_data = {"word_phrase": "ett äpple", "include_translation": True, "include_extra_info": True}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] == "an apple"
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] == "en-word, noun, base form: äpple"

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.include_translation is True
    assert call_args.include_extra_info is True


def test_improve_vocabulary_extra_info_only(client_with_mock_service):
    """Test vocabulary improvement endpoint with only extra_info."""
    client, mock_service = client_with_mock_service

    # Mock service response with only extra_info
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase="Jag äter ett äpple varje dag.", extra_info="en-word, noun, base form: äpple"
    )
    mock_service.improve_item.return_value = mock_response

    # Test request with only extra_info
    request_data = {"word_phrase": "ett äpple", "include_translation": False, "include_extra_info": True}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] == "en-word, noun, base form: äpple"
