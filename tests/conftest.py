"""
Shared fixtures and configuration for tests.

This module provides reusable test fixtures for testing,
including database setup for unit tests.
"""

import os

# Set test environment file BEFORE any imports that could trigger config loading
os.environ["ENV_FILE"] = ".env.test"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from runestone.db.database import Base  # noqa: E402
from runestone.db.user_repository import UserRepository  # noqa: E402
from runestone.db.vocabulary_repository import VocabularyRepository  # noqa: E402


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Dispose the engine to close all connections
        engine.dispose()


@pytest.fixture
def user_repository(db_session):
    """Create a UserRepository instance."""
    return UserRepository(db_session)


@pytest.fixture
def vocabulary_repository(db_session):
    """Create a VocabularyRepository instance."""
    return VocabularyRepository(db_session)
