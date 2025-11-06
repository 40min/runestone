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
