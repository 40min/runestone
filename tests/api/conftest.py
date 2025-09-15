"""
Shared fixtures and configuration for API tests.

This module provides reusable test fixtures for API testing,
including database setup and test client configuration.
"""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.api.main import app
from runestone.db.database import Base, get_db


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a test client with file-based database for testing."""
    # Use a temporary database file for testing
    test_db_url = "sqlite:///./test_vocabulary.db"

    # Override the database dependency for testing
    def override_get_db():
        engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

    # Clean up the test database file
    if os.path.exists("./test_vocabulary.db"):
        os.remove("./test_vocabulary.db")


@pytest.fixture(scope="function")
def client_no_db() -> TestClient:
    """Create a test client without database setup for mocked tests."""
    return TestClient(app)
