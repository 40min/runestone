"""
Shared fixtures for services tests.
"""

import os
import tempfile

import pytest

# ==============================================================================
# User Service Fixtures
# ==============================================================================


@pytest.fixture
def mock_user_repo():
    """Create a mocked UserRepository."""
    from unittest.mock import AsyncMock, Mock

    mock = Mock()
    mock.get_by_id = AsyncMock()
    mock.get_by_email = AsyncMock()
    mock.update = AsyncMock()
    mock.increment_pages_recognised_count = AsyncMock()
    mock.clear_user_memory = AsyncMock()
    mock.update_user_memory = AsyncMock()
    return mock


@pytest.fixture
def mock_vocab_repo():
    """Create a mocked VocabularyRepository."""
    from unittest.mock import AsyncMock, Mock

    mock = Mock()
    # Set default return values for count methods used by get_user_profile
    mock.get_words_in_learn_count = AsyncMock(return_value=0)
    mock.get_words_skipped_count = AsyncMock(return_value=0)
    mock.get_overall_words_count = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def user_service(mock_user_repo, mock_vocab_repo):
    """Create a UserService instance with mocked repositories."""
    from runestone.services.user_service import UserService

    return UserService(mock_user_repo, mock_vocab_repo)


@pytest.fixture
def user():
    """Create a real User instance for testing."""
    from datetime import datetime

    from runestone.db.models import User

    return User(
        id=1,
        email="test@example.com",
        hashed_password="hashedpassword",
        name="Test User",
        surname="Testsson",
        timezone="UTC",
        pages_recognised_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


# ==============================================================================
# State Fixtures
# ==============================================================================


@pytest.fixture
def temp_state_file():
    """Create a temporary state file with default configuration."""
    import json

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
