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
    from unittest.mock import Mock

    return Mock()


@pytest.fixture
def mock_vocab_repo():
    """Create a mocked VocabularyRepository."""
    from unittest.mock import Mock

    mock = Mock()
    # Set default return values for count methods used by get_user_profile
    mock.get_words_in_learn_count.return_value = 0
    mock.get_words_learned_count.return_value = 0
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
# Grammar Service Fixtures
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
