"""
Shared fixtures and configuration for API tests.

This module provides reusable test fixtures for API testing,
including database setup and test client configuration.
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runestone.api.main import app
from runestone.auth.dependencies import get_current_user
from runestone.dependencies import get_llm_client


@pytest.fixture(scope="function")
def mock_llm_client():
    """Create a mock LLM client that doesn't make external API calls."""
    mock_client = Mock()
    # Mock the improve_vocabulary_item method to return a sample response
    mock_client.improve_vocabulary_item.return_value = "Mock extra info for vocabulary enrichment"
    return mock_client


@pytest.fixture(scope="function")
def client(client_with_overrides, db_with_test_user):
    """
    Create a test client with in-memory database and mocked LLM client for testing.

    This fixture is a simple consumer of the client_with_overrides factory
    with default parameters (empty overrides dict).
    """
    db, test_user = db_with_test_user

    # Create a vocabulary repository and service that use the same database session
    from unittest.mock import Mock

    from runestone.db.vocabulary_repository import VocabularyRepository
    from runestone.services.vocabulary_service import VocabularyService

    # Mock settings to avoid dependency injection issues
    mock_settings = Mock()
    mock_settings.vocabulary_enrichment_enabled = True

    # Create the repository and service with the test database session
    vocab_repo = VocabularyRepository(db)
    vocab_service = VocabularyService(vocab_repo, mock_settings, Mock())

    client_gen = client_with_overrides(vocabulary_service=vocab_service)
    client, mocks = next(client_gen)

    yield client

    # Cleanup is handled by the client_with_overrides fixture


@pytest.fixture(scope="function")
def client_no_db() -> TestClient:
    """Create a test client without database setup for mocked tests."""
    from fastapi import HTTPException, status

    from runestone.dependencies import get_user_service, get_vocabulary_service

    # Mock services to avoid database calls for unauthorized tests
    mock_user_service = Mock()
    mock_vocab_service = Mock()

    def override_get_current_user():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    def override_get_user_service():
        return mock_user_service

    def override_get_vocabulary_service():
        return mock_vocab_service

    # Apply overrides for authentication
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_user_service] = override_get_user_service
    app.dependency_overrides[get_vocabulary_service] = override_get_vocabulary_service

    client = TestClient(app)

    yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_with_overrides(mock_llm_client, db_with_test_user):
    """
    Factory fixture for creating test clients with customizable dependency overrides.

    This eliminates duplication by providing a single, flexible client creation
    function that can be customized for different test scenarios.

    Args:
        mock_llm_client: Mocked LLM client from conftest
        db_with_test_user: Database session with test user from root conftest

    Returns:
        function: Factory function that accepts override parameters

    Example:
        def test_example(client_with_overrides, mock_vocabulary_service):
            client, mocks = client_with_overrides(
                vocabulary_service=mock_vocabulary_service
            )
            response = client.post("/api/vocabulary/improve", json=data)
            assert response.status_code == 200
    """
    from runestone.db.database import get_db
    from runestone.dependencies import get_grammar_service, get_vocabulary_service

    def _create_client(
        vocabulary_service=None,
        grammar_service=None,
        processor=None,
        llm_client=None,
        current_user=None,
        db_override=None,
    ):
        db, test_user = db_with_test_user

        def override_get_db():
            """
            Override database dependency to ensure consistent session use.

            This is critical for test data visibility across all API operations
            within a single test function.
            """
            yield db

        def override_get_llm_client():
            return llm_client or mock_llm_client

        def override_get_current_user():
            return current_user or test_user

        # Apply overrides
        overrides = {
            get_llm_client: override_get_llm_client,
            get_current_user: override_get_current_user,
            get_db: db_override or override_get_db,
        }

        if vocabulary_service:
            overrides[get_vocabulary_service] = lambda: vocabulary_service
        if grammar_service:
            overrides[get_grammar_service] = lambda: grammar_service
        if processor:
            from runestone.dependencies import get_runestone_processor

            overrides[get_runestone_processor] = lambda: processor

        for dep, override in overrides.items():
            app.dependency_overrides[dep] = override

        client = TestClient(app)

        # Add helper method to ensure database state
        def sync_db():
            """Sync database to ensure all pending changes are committed and visible."""
            try:
                if hasattr(db, "is_active") and db.is_active:
                    db.commit()
                    db.flush()
            except Exception:
                pass

        client.sync_db = sync_db

        # Return client and mocks for easy access
        mocks = {
            "vocabulary_service": vocabulary_service,
            "grammar_service": grammar_service,
            "processor": processor,
            "llm_client": llm_client or mock_llm_client,
            "current_user": current_user or test_user,
        }

        yield client, mocks

        # Cleanup
        app.dependency_overrides.clear()

    return _create_client


@pytest.fixture(scope="function")
def client_with_mock_processor(client_with_overrides, mock_processor):
    """
    Create a test client with mocked RunestoneProcessor using the client_with_overrides factory.

    Returns:
        tuple: (TestClient, Mock) - The test client and mock processor instance

    Example:
        def test_resource_endpoint(client_with_mock_processor):
            client, mock_processor = client_with_mock_processor
            mock_processor.run_resource_search.return_value = "custom response"
            response = client.post("/api/resources", json=data)
            assert response.status_code == 200
    """
    client_gen = client_with_overrides(processor=mock_processor)
    client, mocks = next(client_gen)
    return client, mocks["processor"]


# ==============================================================================
# Specialized Client Fixtures
# ==============================================================================


@pytest.fixture(scope="function")
def client_with_mock_vocabulary_service(client_with_overrides, mock_vocabulary_service):
    """
    Create a test client with mocked vocabulary service.

    Returns:
        tuple: (TestClient, Mock) - The test client and mock vocabulary service

    Example:
        def test_improve_endpoint(client_with_mock_vocabulary_service):
            client, mock_service = client_with_mock_vocabulary_service
            mock_service.improve_item.return_value = custom_response
            response = client.post("/api/vocabulary/improve", json=data)
            assert response.status_code == 200
    """
    client_gen = client_with_overrides(vocabulary_service=mock_vocabulary_service)
    client, mocks = next(client_gen)
    return client, mock_vocabulary_service


@pytest.fixture(scope="function")
def client_with_mock_grammar_service(client_with_overrides, mock_grammar_service):
    """
    Create a test client with mocked grammar service.

    Returns:
        tuple: (TestClient, Mock) - The test client and mock grammar service

    Example:
        def test_grammar_endpoint(client_with_mock_grammar_service):
            client, mock_service = client_with_mock_grammar_service
            mock_service.list_cheatsheets.return_value = [...]
            response = client.get("/api/grammar/cheatsheets")
            assert response.status_code == 200
    """
    client_gen = client_with_overrides(grammar_service=mock_grammar_service)
    client, mocks = next(client_gen)
    return client, mock_grammar_service
