from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runestone.api.main import app
from runestone.api.schemas import ImprovementMode, VocabularyImproveRequest, VocabularyImproveResponse
from runestone.auth.dependencies import get_current_user
from runestone.dependencies import get_llm_client, get_vocabulary_service


# TODO: such fixtures should be in conftest.py, we have something
# similar. It is needed to generalise common setup and create
# customised fixtures if something need to be mocked like here
@pytest.fixture
def client_with_mock_service(mock_llm_client):
    """Create a test client with mocked vocabulary service."""
    # Create mock service
    mock_service = Mock()

    # Use the same setup as the main client fixture
    import uuid

    db_name = f"memdb{uuid.uuid4().hex}"
    test_db_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from runestone.db.database import Base, get_db

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False, "uri": True})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_llm_client():
        return mock_llm_client

    def override_get_current_user():
        # Create a simple test user mock
        test_user = Mock()
        test_user.id = 1
        test_user.email = "test@example.com"
        test_user.name = "Test"
        test_user.surname = "User"
        return test_user

    def override_get_vocabulary_service():
        return mock_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_get_llm_client
    app.dependency_overrides[get_vocabulary_service] = override_get_vocabulary_service
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)

    yield client, mock_service

    # Clean up
    app.dependency_overrides.clear()


def test_improve_vocabulary_success(client_with_mock_service):
    """Test successful vocabulary improvement endpoint with ALL_FIELDS mode."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation="an apple", example_phrase="Jag äter ett äpple varje dag.", extra_info="en-word, noun"
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] == "an apple"
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] == "en-word, noun"

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.ALL_FIELDS


def test_improve_vocabulary_example_only(client_with_mock_service):
    """Test vocabulary improvement endpoint with EXAMPLE_ONLY mode."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase="Jag äter ett äpple varje dag.", extra_info=None
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "example_only"}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] is None

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXAMPLE_ONLY


def test_improve_vocabulary_extra_info_only(client_with_mock_service):
    """Test vocabulary improvement endpoint with EXTRA_INFO_ONLY mode."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase=None, extra_info="en-word, noun, base form: äpple"
    )
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "extra_info_only"}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] is None
    assert response_data["extra_info"] == "en-word, noun, base form: äpple"

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXTRA_INFO_ONLY


def test_improve_vocabulary_service_error(client_with_mock_service):
    """Test vocabulary improvement endpoint with service error."""
    client, mock_service = client_with_mock_service

    # Mock service to raise exception
    mock_service.improve_item.side_effect = Exception("LLM service error")

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

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
        "mode": "all_fields"
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
    mock_response = VocabularyImproveResponse(translation=None, example_phrase="", extra_info=None)
    mock_service.improve_item.return_value = mock_response

    # Test request
    request_data = {"word_phrase": "ett äpple", "mode": "all_fields"}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == ""
    assert response_data["extra_info"] is None


def test_improve_vocabulary_default_mode(client_with_mock_service):
    """Test vocabulary improvement endpoint with default mode (EXAMPLE_ONLY)."""
    client, mock_service = client_with_mock_service

    # Mock service response
    mock_response = VocabularyImproveResponse(
        translation=None, example_phrase="Jag äter ett äpple varje dag.", extra_info=None
    )
    mock_service.improve_item.return_value = mock_response

    # Test request without mode (should default to EXAMPLE_ONLY)
    request_data = {"word_phrase": "ett äpple"}

    response = client.post("/api/vocabulary/improve", json=request_data)

    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["translation"] is None
    assert response_data["example_phrase"] == "Jag äter ett äpple varje dag."
    assert response_data["extra_info"] is None

    # Verify service was called correctly
    mock_service.improve_item.assert_called_once()
    call_args = mock_service.improve_item.call_args[0][0]
    assert isinstance(call_args, VocabularyImproveRequest)
    assert call_args.word_phrase == "ett äpple"
    assert call_args.mode == ImprovementMode.EXAMPLE_ONLY
