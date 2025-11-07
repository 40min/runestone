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


# ==============================================================================
# Mock Service Fixtures
# ==============================================================================


@pytest.fixture
def mock_vocabulary_service():
    """Create a standardized mock VocabularyService."""
    from unittest.mock import Mock

    from runestone.api.schemas import VocabularyImproveResponse

    mock = Mock()
    # Set sensible defaults
    mock.improve_item.return_value = VocabularyImproveResponse(
        translation="mock translation", example_phrase="mock example", extra_info="mock info"
    )
    mock.save_vocabulary.return_value = {"message": "Vocabulary saved successfully"}
    mock.get_vocabulary.return_value = []
    return mock


@pytest.fixture
def mock_grammar_service():
    """Create a standardized mock GrammarService."""
    from unittest.mock import Mock

    mock = Mock()
    mock.list_cheatsheets.return_value = []
    mock.get_cheatsheet_content.return_value = "# Mock Content"
    return mock


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


# ==============================================================================
# Factory Fixtures for Test Data
# ==============================================================================


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


@pytest.fixture
def mock_user_factory():
    """Factory for creating mock user objects."""
    from unittest.mock import Mock

    def _create(id=1, email="test@example.com", name="Test", surname="User"):
        user = Mock()
        user.id = id
        user.email = email
        user.name = name
        user.surname = surname
        return user

    return _create


# ==============================================================================
# Temporary File/Directory Fixtures
# ==============================================================================


@pytest.fixture
def temp_state_file():
    """Create a temporary state file with default configuration."""
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        default_state = {
            "update_offset": 0,
            "users": {
                "active_user": {"db_user_id": 1, "chat_id": 123, "is_active": True, "daily_selection": []},
                "inactive_user": {"db_user_id": 2, "chat_id": 456, "is_active": False, "daily_selection": []},
            },
        }
        json.dump(default_state, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_cheatsheets_dir():
    """Create a temporary directory with test cheatsheet files."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test markdown files
        files = {
            "adjectiv-komparation.md": "# Adjectiv Komparation\n\nContent about adjective comparison.",
            "objectspronomen.md": "# Objectspronomen\n\nContent about object pronouns.",
            "presens-perfect.md": "# Presens Perfect\n\nContent about present perfect tense.",
            "pronunciation.md": "# Pronunciation\n\nContent about Swedish pronunciation.",
            "swedish_adjectives_cheatsheet.md": (
                "# Swedish Adjectives Cheatsheet\n\nContent about Swedish adjectives."
            ),
        }

        for filename, content in files.items():
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # Create a non-md file to ensure it's filtered out
        non_md_file = os.path.join(temp_dir, "not_a_cheatsheet.txt")
        with open(non_md_file, "w", encoding="utf-8") as f:
            f.write("This should be ignored")

        yield temp_dir


@pytest.fixture
def temp_cheatsheets_with_categories():
    """Create a temporary directory with categorized cheatsheet files."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create root level files (General category)
        root_files = {
            "pronunciation.md": "# Pronunciation\n\nContent about pronunciation.",
            "swedish_adjectives.md": "# Swedish Adjectives\n\nContent about adjectives.",
        }

        for filename, content in root_files.items():
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # Create subdirectories with categorized files
        verbs_dir = os.path.join(temp_dir, "verbs")
        os.makedirs(verbs_dir, exist_ok=True)
        verbs_files = {
            "hjalpverb.md": "# Hjalpverb\n\nContent about auxiliary verbs.",
            "verb-forms.md": "# Verb Forms\n\nContent about verb forms.",
        }

        for filename, content in verbs_files.items():
            filepath = os.path.join(verbs_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # Create adjectives subdirectory
        adj_dir = os.path.join(temp_dir, "adjectives")
        os.makedirs(adj_dir, exist_ok=True)
        adj_files = {
            "adjectiv-komparation.md": "# Adjectiv Komparation\n\nContent about adjective comparison.",
        }

        for filename, content in adj_files.items():
            filepath = os.path.join(adj_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        yield temp_dir
