"""
Shared fixtures and configuration for API tests.

This module provides reusable test fixtures for API testing,
including database setup and test client configuration.
"""

from typing import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.api.main import app
from runestone.auth.dependencies import get_current_user
from runestone.db.database import Base, get_db
from runestone.db.models import User
from runestone.dependencies import get_llm_client, get_runestone_processor


@pytest.fixture(scope="function")
def mock_llm_client():
    """Create a mock LLM client that doesn't make external API calls."""
    mock_client = Mock()
    # Mock the improve_vocabulary_item method to return a sample response
    mock_client.improve_vocabulary_item.return_value = "Mock extra info for vocabulary enrichment"
    return mock_client


@pytest.fixture(scope="function")
def client(mock_llm_client) -> Generator[TestClient, None, None]:
    """Create a test client with in-memory database and mocked LLM client for testing."""
    # Use a shared in-memory database for each test
    # The file:memdb?mode=memory&cache=shared syntax creates a shared in-memory database
    # that can be accessed by multiple connections within the same process
    import uuid

    db_name = f"memdb{uuid.uuid4().hex}"
    test_db_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

    # Create a single engine for all tests in this fixture
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False, "uri": True})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create a test user with unique email to avoid conflicts
    import uuid

    unique_email = f"test-{uuid.uuid4()}@example.com"
    test_user = User(
        name="Test User",
        surname="Testsson",
        email=unique_email,
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",  # "password"
    )
    db = SessionLocal()
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    db.close()

    # Override the database dependency for testing
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Override the LLM client dependency to use mocked client
    def override_get_llm_client():
        return mock_llm_client

    # Override the current user dependency to use test user
    def override_get_current_user():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == unique_email).first()
            return user
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_get_llm_client
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_no_db() -> TestClient:
    """Create a test client without database setup for mocked tests."""
    return TestClient(app)


@pytest.fixture(scope="function")
def client_with_mock_processor(client):
    """Fixture to provide a client with a mocked RunestoneProcessor.

    This fixture automatically sets up the dependency override and cleans it up
    after the test, reducing boilerplate in tests that need to mock the processor.

    Yields:
        tuple: (TestClient, Mock) - The test client and the mocked processor instance
    """
    mock_processor_instance = Mock()
    client.app.dependency_overrides[get_runestone_processor] = lambda: mock_processor_instance

    yield client, mock_processor_instance

    # Teardown: clear the override automatically after the test runs
    client.app.dependency_overrides.clear()


# ==============================================================================
# Specialized Client Fixtures
# ==============================================================================


@pytest.fixture(scope="function")
def client_with_mock_vocabulary_service(mock_vocabulary_service):
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
    from sqlalchemy.pool import StaticPool

    from runestone.dependencies import get_vocabulary_service

    # Database setup
    test_db_url = "sqlite:///:memory:"

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create test user
    import uuid

    unique_email = f"test-{uuid.uuid4()}@example.com"
    test_user = User(
        name="Test User",
        surname="Testsson",
        email=unique_email,
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
    )
    db = SessionLocal()
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    db.close()

    # Setup overrides
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_llm_client():
        from unittest.mock import Mock

        return Mock()

    def override_get_current_user():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == unique_email).first()
            return user
        finally:
            db.close()

    # Apply overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_get_llm_client
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_vocabulary_service] = lambda: mock_vocabulary_service

    client = TestClient(app)

    yield client, mock_vocabulary_service

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def client_with_mock_grammar_service(mock_grammar_service):
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
    from sqlalchemy.pool import StaticPool

    from runestone.dependencies import get_grammar_service

    # Database setup
    test_db_url = "sqlite:///:memory:"

    engine = create_engine(test_db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create test user
    import uuid

    unique_email = f"test-{uuid.uuid4()}@example.com"
    test_user = User(
        name="Test User",
        surname="Testsson",
        email=unique_email,
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
    )
    db = SessionLocal()
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    db.close()

    # Setup overrides
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_llm_client():
        from unittest.mock import Mock

        return Mock()

    def override_get_current_user():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == unique_email).first()
            return user
        finally:
            db.close()

    # Apply overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_get_llm_client
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_grammar_service] = lambda: mock_grammar_service

    client = TestClient(app)

    yield client, mock_grammar_service

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client_with_custom_user(client):
    """
    Create a test client with a custom mock user.

    Returns:
        function: Factory function that creates client with custom user

    Example:
        def test_user_specific(client_with_custom_user):
            client, user = client_with_custom_user(user_id=42, email="custom@test.com")
            response = client.get("/api/user/profile")
            assert response.status_code == 200
    """

    def _create(user_id=1, email="test@example.com", name="Test", surname="User"):
        from unittest.mock import Mock

        mock_user = Mock()
        mock_user.id = user_id
        mock_user.email = email
        mock_user.name = name
        mock_user.surname = surname

        # Override current user
        from runestone.auth.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: mock_user
        return client, mock_user

    return _create
