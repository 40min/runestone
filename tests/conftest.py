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
from sqlalchemy.pool import StaticPool  # noqa: E402

from runestone.db.database import Base  # noqa: E402
from runestone.db.models import User  # noqa: E402
from runestone.db.user_repository import UserRepository  # noqa: E402
from runestone.db.vocabulary_repository import VocabularyRepository  # noqa: E402


@pytest.fixture(scope="function")
def db_engine():
    """
    Create a fresh test database engine for each test (complete isolation).

    Uses in-memory SQLite to ensure:
    - No data pollution between tests
    - Safe parallel test execution
    - Easy debugging (each test starts clean)

    Performance: In-memory databases are fast enough that per-test
    creation has minimal impact (~1-5ms overhead per test).
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session_factory(db_engine):
    """Create a session factory for the test database."""
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture(scope="function")
def db_with_test_user(db_session_factory):
    """
    Create a database session with a pre-created test user.

    Each test gets a fresh database with a unique test user.
    No cleanup needed as the entire database is disposed after the test.

    Returns:
        tuple: (Session, User) - Database session and test user
    """
    import uuid

    db = db_session_factory()
    unique_email = f"test-{uuid.uuid4()}@example.com"
    test_user = User(
        name="Test User",
        surname="Testsson",
        email=unique_email,
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

    try:
        yield db, test_user
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Create a fresh database session for each test.

    Each test gets a completely isolated database session with no
    data from previous tests. This ensures test independence and
    makes debugging easier.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def user_repository(db_session):
    """Create a UserRepository instance."""
    return UserRepository(db_session)


@pytest.fixture
def vocabulary_repository(db_session):
    """Create a VocabularyRepository instance."""
    return VocabularyRepository(db_session)


@pytest.fixture
def mock_processor():
    """Create a standardized mock RunestoneProcessor."""
    from unittest.mock import Mock

    from runestone.schemas.analysis import ContentAnalysis, GrammarFocus, SearchNeeded
    from runestone.schemas.ocr import OCRResult, RecognitionStatistics

    mock = Mock()
    mock.run_ocr.return_value = OCRResult(
        transcribed_text="mock text",
        recognition_statistics=RecognitionStatistics(
            total_elements=10, successfully_transcribed=10, unclear_uncertain=0, unable_to_recognize=0
        ),
    )
    mock.run_analysis.return_value = ContentAnalysis(
        grammar_focus=GrammarFocus(
            has_explicit_rules=False, topic="mock topic", explanation="mock explanation", rules=None
        ),
        vocabulary=[],
        core_topics=[],
        search_needed=SearchNeeded(should_search=False, query_suggestions=[]),
    )
    return mock


@pytest.fixture
def vocabulary_item_factory():
    """Factory for creating VocabularyItemCreate instances."""
    from runestone.api.schemas import VocabularyItemCreate

    def _create(
        word_phrase="test word", translation="test translation", example_phrase="Test example.", extra_info=None
    ):
        return VocabularyItemCreate(
            word_phrase=word_phrase, translation=translation, example_phrase=example_phrase, extra_info=extra_info
        )

    return _create


@pytest.fixture
def vocabulary_model_factory():
    """Factory for creating VocabularyModel instances."""
    from datetime import datetime, timezone

    from runestone.db.models import Vocabulary

    def _create(
        user_id=1,
        word_phrase="",
        translation="",
        example_phrase=None,
        created_at=None,
        in_learn=True,
        last_learned=None,
        learned_times=0,
    ):
        """Create a VocabularyModel instance with provided or default values."""
        return Vocabulary(
            user_id=user_id,
            word_phrase=word_phrase,
            translation=translation,
            example_phrase=example_phrase,
            created_at=created_at or datetime.now(timezone.utc),
            in_learn=in_learn,
            last_learned=last_learned,
            learned_times=learned_times,
        )

    return _create
