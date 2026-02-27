"""
Shared fixtures and configuration for tests.

This module provides reusable test fixtures for testing,
including database setup for unit tests.
"""

import os

# Set test environment file BEFORE any imports that could trigger config loading
os.environ["ENV_FILE"] = ".env.test"

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from runestone.config import settings  # noqa: E402
from runestone.db.database import Base  # noqa: E402
from runestone.db.models import User  # noqa: E402
from runestone.db.user_repository import UserRepository  # noqa: E402
from runestone.db.vocabulary_repository import VocabularyRepository  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def db_engine():
    """
    Create a fresh test database engine for each test.
    """
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
def db_session_factory(db_engine):
    """Create a session factory for the test database."""
    return async_sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture(scope="function")
async def db_with_test_user(db_session_factory):
    """
    Create a database session with a pre-created test user.

    Each test gets a fresh database with a unique test user.
    """
    import uuid

    async with db_session_factory() as db:
        unique_email = f"test-{uuid.uuid4()}@example.com"
        test_user = User(
            name="Test User",
            surname="Testsson",
            email=unique_email,
            hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
            timezone="UTC",
            pages_recognised_count=0,
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)

        yield db, test_user


@pytest.fixture(scope="function")
async def db_session(db_session_factory):
    """
    Create a fresh database session for each test.
    """
    async with db_session_factory() as db:
        yield db
        await db.rollback()


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
    from unittest.mock import AsyncMock, Mock

    from runestone.schemas.analysis import ContentAnalysis, GrammarFocus
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
    )
    mock.run_analysis = AsyncMock(return_value=mock.run_analysis.return_value)
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


# ==============================================================================
# Cheatsheet Test Fixtures
# ==============================================================================


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
