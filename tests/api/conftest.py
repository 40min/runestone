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
from runestone.db.database import Base, get_db
from runestone.dependencies import get_runestone_processor


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a test client with in-memory database for testing."""
    # Use a shared in-memory database for faster testing
    # The 'file::memory:?cache=shared' URI allows multiple connections to share the same in-memory database
    test_db_url = "sqlite:///file::memory:?cache=shared&uri=true"

    # Create a single engine for all tests in this fixture
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False, "uri": True})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Override the database dependency for testing
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

    # Dispose the engine to close all connections
    engine.dispose()


@pytest.fixture(scope="function")
def client_no_db() -> TestClient:
    """Create a test client without database setup for mocked tests."""
    return TestClient(app)


@pytest.fixture(scope="function")
def client_with_mock_processor(client_no_db):
    """Fixture to provide a client with a mocked RunestoneProcessor.

    This fixture automatically sets up the dependency override and cleans it up
    after the test, reducing boilerplate in tests that need to mock the processor.

    Yields:
        tuple: (TestClient, Mock) - The test client and the mocked processor instance
    """
    mock_processor_instance = Mock()
    client_no_db.app.dependency_overrides[get_runestone_processor] = lambda: mock_processor_instance

    yield client_no_db, mock_processor_instance

    # Teardown: clear the override automatically after the test runs
    client_no_db.app.dependency_overrides.clear()
