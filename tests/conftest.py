"""
Shared fixtures and configuration for tests.

This module provides reusable test fixtures for testing,
including database setup for unit tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.db.database import Base
from runestone.db.repository import VocabularyRepository


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


@pytest.fixture
def vocabulary_repository(db_session):
    """Create a VocabularyRepository instance."""
    return VocabularyRepository(db_session)