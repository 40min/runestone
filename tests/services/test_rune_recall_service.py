import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.runestone.db.database import Base
from src.runestone.db.models import Vocabulary
from src.runestone.db.repository import VocabularyRepository
from src.runestone.services.rune_recall_service import RuneRecallService
from src.runestone.state.state_manager import StateManager


@pytest.fixture
def temp_state_file():
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
def state_manager(temp_state_file):
    StateManager._reset_for_testing()
    return StateManager(temp_state_file)


@pytest.fixture
def test_db():
    """Create a test database with sample vocabulary data."""
    test_db_url = "sqlite:///./test_recall.db"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        # Add sample vocabulary for user 1
        words = [
            Vocabulary(
                user_id=1,
                word_phrase="hello",
                translation="hej",
                example_phrase="Hello, how are you?",
                in_learn=True,
                last_learned=None,
            ),
            Vocabulary(
                user_id=1,
                word_phrase="goodbye",
                translation="hej då",
                example_phrase="Goodbye, see you later!",
                in_learn=True,
                last_learned=None,
            ),
            Vocabulary(
                user_id=1,
                word_phrase="thank you",
                translation="tack",
                example_phrase="Thank you for your help.",
                in_learn=True,
                last_learned=None,
            ),
            Vocabulary(
                user_id=2,
                word_phrase="water",
                translation="vatten",
                example_phrase="I need water.",
                in_learn=True,
                last_learned=None,
            ),
        ]
        db.add_all(words)
        db.commit()

        yield db
    finally:
        db.close()
        if os.path.exists("./test_recall.db"):
            os.remove("./test_recall.db")


@pytest.fixture
def vocabulary_repository(test_db):
    """Create a VocabularyRepository instance."""
    return VocabularyRepository(test_db)


@pytest.fixture
def rune_recall_service(vocabulary_repository, state_manager):
    return RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token")


def test_init_with_token(vocabulary_repository, state_manager):
    service = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token")
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"
    assert service.words_per_day == 5
    assert service.cooldown_days == 7


def test_init_with_custom_params(vocabulary_repository, state_manager):
    service = RuneRecallService(
        vocabulary_repository, state_manager, bot_token="test_token", words_per_day=3, cooldown_days=5
    )
    assert service.words_per_day == 3
    assert service.cooldown_days == 5


def test_init_without_token(vocabulary_repository, state_manager):
    with patch("src.runestone.services.rune_recall_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "config_token"
        service = RuneRecallService(vocabulary_repository, state_manager)
        assert service.bot_token == "config_token"


def test_init_no_token_raises_error(vocabulary_repository, state_manager):
    with patch("src.runestone.services.rune_recall_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        with pytest.raises(ValueError, match="Telegram bot token is required"):
            RuneRecallService(vocabulary_repository, state_manager)


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_success(mock_client_class, rune_recall_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    word = {"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": "Hello, how are you?"}

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    expected_message = "🇸🇪 **hello**\n🇬🇧 hej\n\n💡 *Example:* Hello, how are you?"
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "Markdown"},
    )


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_without_example(mock_client_class, rune_recall_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    word = {"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": None}

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    expected_message = "🇸🇪 **hello**\n🇬🇧 hej"
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "Markdown"},
    )


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_failure(mock_client_class, rune_recall_service):
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Network error")
    mock_client_class.return_value.__enter__.return_value = mock_client

    word = {"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": None}

    result = rune_recall_service._send_word_message(123, word)
    assert result is False


def test_select_daily_portion(rune_recall_service):
    # Test selecting words for user 1
    words = rune_recall_service._select_daily_portion(1)

    assert len(words) == 3  # Should select all 3 words for user 1
    assert words[0]["word_phrase"] == "hello"  # Order by ID since timestamps are identical
    assert words[1]["word_phrase"] == "goodbye"
    assert words[2]["word_phrase"] == "thank you"


def test_select_daily_portion_with_recent_history(rune_recall_service, test_db):
    # Simulate that the first word was learned recently by setting last_learned
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    hello_word.last_learned = datetime.now() - timedelta(days=1)  # Learned yesterday
    test_db.commit()

    words = rune_recall_service._select_daily_portion(1)

    assert len(words) == 2  # Should exclude the recently learned word
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases  # Should not include recently learned word


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_new_portion(mock_client_class, rune_recall_service, test_db, state_manager):

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock word selection to return 3 words
    mock_words = [
        {"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": "Hello"},
        {"id": 2, "word_phrase": "goodbye", "translation": "hej då", "example_phrase": "Goodbye"},
        {"id": 3, "word_phrase": "thank you", "translation": "tack", "example_phrase": "Thank you"},
    ]

    # Get user data
    user_data = state_manager.get_user("active_user")

    # Process recall word for active user (no existing portion)
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_words):
        rune_recall_service._process_user_recall_word("active_user", user_data)

    # Check that daily selection was created
    user_data = state_manager.get_user("active_user")
    assert len(user_data.daily_selection) == 3  # All 3 word items
    assert user_data.next_word_index == 1  # First word sent

    # Check that message was sent
    mock_client.post.assert_called_once()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_all_sent(mock_client_class, rune_recall_service, test_db, state_manager):

    # Mock HTTP client
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Set up selection with all words sent
    state_manager.update_user(
        "active_user",
        {
            "db_user_id": 1,
            "chat_id": 123,
            "is_active": True,
            "daily_selection": [[1, "hello"]],
            "next_word_index": 1,  # All words sent
        },
    )

    user_data = state_manager.get_user("active_user")

    # Process recall word
    rune_recall_service._process_user_recall_word("active_user", user_data)

    # Should send a message (resets to index 0 and sends next word)
    mock_client.post.assert_called_once()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_missing_data(mock_client_class, rune_recall_service, state_manager):
    # Mock HTTP client
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Update existing user to have missing chat_id
    state_manager.update_user(
        "active_user", {"db_user_id": 1, "chat_id": None, "is_active": True, "daily_selection": []}
    )

    user_data = state_manager.get_user("active_user")

    rune_recall_service._process_user_recall_word("active_user", user_data)

    # Should not send any messages
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_next_recall_word_multiple_users(mock_client_class, rune_recall_service, state_manager):
    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock the word selection to return empty (to avoid database dependency)
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=[]):
        rune_recall_service.send_next_recall_word()

    # Should not send any messages since no words selected
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_next_recall_word_with_errors(mock_client_class, rune_recall_service, test_db, state_manager):

    # Mock HTTP client to fail
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Network error")
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock word selection to return some words (using existing word ID from test_db)
    mock_words = [{"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": "Hello, how are you?"}]

    user_data = state_manager.get_user("active_user")

    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_words):
        # Should not raise exception, just log errors
        rune_recall_service._process_user_recall_word("active_user", user_data)

    # Should have attempted to send message despite error
    mock_client.post.assert_called_once()


def test_daily_selection_cleanup(rune_recall_service, test_db, state_manager):
    """Test that old daily selection entries are cleaned up."""

    # Add user with daily selection data
    state_manager.update_user(
        "active_user",
        {
            "db_user_id": 1,
            "chat_id": 123,
            "is_active": True,
            "daily_selection": [[1, "word1"], [2, "word2"]],  # Existing selection
        },
    )

    # Mock word selection and message sending (using existing word ID from test_db)
    mock_words = [{"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": "Hello, how are you?"}]

    user_data = state_manager.get_user("active_user")

    with (
        patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_words),
        patch.object(rune_recall_service, "_send_word_message", return_value=True),
    ):

        rune_recall_service._process_user_recall_word("active_user", user_data)

    # Check that selection is not updated since it already exists
    user_data = state_manager.get_user("active_user")
    assert len(user_data.daily_selection) == 2  # Existing selection remains


# Tests for new recall functionality


@patch("src.runestone.services.rune_recall_service.datetime")
@patch("src.runestone.services.rune_recall_service.settings")
def test_send_next_recall_word_within_hours(mock_settings, mock_datetime, rune_recall_service):
    """Test that recall words are sent when within recall hours."""
    # Mock current time to be 10 AM
    mock_datetime.now.return_value.hour = 10

    # Mock settings
    mock_settings.recall_start_hour = 9
    mock_settings.recall_end_hour = 22

    with patch.object(rune_recall_service, "_process_user_recall_word") as mock_process:
        rune_recall_service.send_next_recall_word()

    # Should process users since we're within hours
    mock_process.assert_called()


@patch("src.runestone.services.rune_recall_service.settings")
def test_send_next_recall_word_outside_hours(mock_settings, rune_recall_service):
    """Test that recall words are not sent when outside recall hours."""
    # Mock settings
    mock_settings.recall_start_hour = 9
    mock_settings.recall_end_hour = 22

    with patch("src.runestone.services.rune_recall_service.datetime") as mock_datetime:
        # Mock current time to be 2 AM
        mock_datetime.now.return_value.hour = 2

        with patch.object(rune_recall_service, "_process_user_recall_word") as mock_process:
            rune_recall_service.send_next_recall_word()

        # Should not process users since we're outside hours
        mock_process.assert_not_called()


# Tests for cooldown functionality


def test_rune_recall_service_different_cooldown_periods(vocabulary_repository):
    """Test RuneRecallService with different cooldown periods."""
    state_manager = MagicMock()

    # Test default cooldown (7 days)
    service_default = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token")
    assert service_default.cooldown_days == 7

    # Test custom cooldown
    service_custom = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token", cooldown_days=3)
    assert service_custom.cooldown_days == 3

    # Test zero cooldown (should allow immediate repetition)
    service_zero = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token", cooldown_days=0)
    assert service_zero.cooldown_days == 0


def test_select_daily_portion_different_cooldown_periods(test_db):
    """Test daily portion selection with different cooldown periods."""
    # Create VocabularyRepository and services with different cooldown periods
    vocabulary_repository = VocabularyRepository(test_db)
    state_manager = MagicMock()
    service = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token", cooldown_days=3)

    # Set up test data: word learned 2 days ago
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    hello_word.last_learned = datetime.now() - timedelta(days=2)
    test_db.commit()

    # With 3-day cooldown, word should be excluded
    words = service._select_daily_portion(1)
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases

    # Create service with 1-day cooldown
    service_short = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token", cooldown_days=1)

    # With 1-day cooldown, word should be included
    words = service_short._select_daily_portion(1)
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" in word_phrases


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_updates_last_learned(mock_client_class, rune_recall_service, test_db, state_manager):
    """Test that processing recall word updates last_learned timestamp."""

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock word selection to return 3 words
    mock_words = [
        {"id": 1, "word_phrase": "hello", "translation": "hej", "example_phrase": "Hello"},
        {"id": 2, "word_phrase": "goodbye", "translation": "hej då", "example_phrase": "Goodbye"},
        {"id": 3, "word_phrase": "thank you", "translation": "tack", "example_phrase": "Thank you"},
    ]

    # Get initial state of a word
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    initial_last_learned = hello_word.last_learned
    word_id = hello_word.id

    # Get user data and process recall word
    user_data = state_manager.get_user("active_user")
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_words):
        rune_recall_service._process_user_recall_word("active_user", user_data)

    # Query the word again from database to see updated state
    updated_word = test_db.query(Vocabulary).filter(Vocabulary.id == word_id).first()

    # Verify last_learned was updated
    assert updated_word.last_learned is not None
    if initial_last_learned is not None:
        assert updated_word.last_learned > initial_last_learned
    # If initial was None, just verify it's now set

    # Verify message was sent
    mock_client.post.assert_called_once()


def test_select_daily_portion_no_words_available(rune_recall_service, test_db):
    """Test daily portion selection when no words are available due to cooldown."""

    # Mark all words as recently learned
    words = test_db.query(Vocabulary).filter(Vocabulary.user_id == 1).all()
    recent_time = datetime.now() - timedelta(days=1)  # Learned yesterday
    for word in words:
        word.last_learned = recent_time
    test_db.commit()

    # Try to select daily portion
    result = rune_recall_service._select_daily_portion(1)

    # Should return empty list since all words are on cooldown
    assert result == []


def test_select_daily_portion_words_per_day_limit(test_db):
    """Test that daily portion respects words_per_day limit."""
    # Create service with limit of 2 words per day
    vocabulary_repository = VocabularyRepository(test_db)
    state_manager = MagicMock()
    service = RuneRecallService(vocabulary_repository, state_manager, bot_token="test_token", words_per_day=2)

    # Ensure all words are available (not on cooldown)
    words = test_db.query(Vocabulary).filter(Vocabulary.user_id == 1).all()
    for word in words:
        word.last_learned = datetime.now() - timedelta(days=10)  # Old enough
    test_db.commit()

    # Select daily portion
    result = service._select_daily_portion(1)

    # Should return only 2 words despite having 3 available
    assert len(result) == 2


def test_select_daily_portion_in_learn_filtering(rune_recall_service, test_db):
    """Test that daily portion only includes words marked as in_learn."""

    # Mark one word as not in learning
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    hello_word.in_learn = False
    test_db.commit()

    # Select daily portion
    words = rune_recall_service._select_daily_portion(1)

    # Should exclude the word not in learning
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases
    assert len(words) == 2  # Should have goodbye and thank you


# Tests for new vocabulary management methods


def test_remove_word_from_daily_selection(rune_recall_service, state_manager):
    """Test removing a word from user's daily_selection."""
    from src.runestone.state.state_types import WordOfDay

    # Setup user with daily selection
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [
        WordOfDay(id_=1, word_phrase="kontanter"),
        WordOfDay(id_=2, word_phrase="hej"),
        WordOfDay(id_=3, word_phrase="tack"),
    ]
    user_data.next_word_index = 1

    # Remove middle word
    result = rune_recall_service.remove_word_from_daily_selection(user_data, "hej")
    assert result is True
    assert len(user_data.daily_selection) == 2
    assert user_data.daily_selection[0].word_phrase == "kontanter"
    assert user_data.daily_selection[1].word_phrase == "tack"
    assert user_data.next_word_index == 1

    # Remove word that doesn't exist
    result = rune_recall_service.remove_word_from_daily_selection(user_data, "nonexistent")
    assert result is False
    assert len(user_data.daily_selection) == 2

    # Remove word that would make index out of bounds
    user_data.next_word_index = 2
    result = rune_recall_service.remove_word_from_daily_selection(user_data, "tack")
    assert result is True
    assert len(user_data.daily_selection) == 1
    assert user_data.next_word_index == 0  # Should reset


def test_replenish_daily_selection_if_empty(rune_recall_service, state_manager):
    """Test replenishing daily_selection when it becomes empty."""
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = []
    user_data.db_user_id = 1

    # Mock new portion selection
    mock_portion = [{"id": 4, "word_phrase": "ny"}, {"id": 5, "word_phrase": "gammal"}]

    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_portion):
        rune_recall_service.replenish_daily_selection_if_empty("active_user", user_data)

    assert len(user_data.daily_selection) == 2
    assert user_data.daily_selection[0].id_ == 4
    assert user_data.daily_selection[0].word_phrase == "ny"
    assert user_data.next_word_index == 0


def test_replenish_daily_selection_not_empty(rune_recall_service, state_manager):
    """Test that replenishment doesn't happen when selection is not empty."""
    from src.runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="existing")]

    with patch.object(rune_recall_service, "_select_daily_portion") as mock_select:
        rune_recall_service.replenish_daily_selection_if_empty("active_user", user_data)

    # Should not call the service
    mock_select.assert_not_called()
    assert len(user_data.daily_selection) == 1


def test_update_user_daily_selection(rune_recall_service, state_manager):
    """Test updating user's daily_selection in state."""
    from src.runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="test")]

    # Mock state manager update
    with patch.object(state_manager, "update_user") as mock_update:
        rune_recall_service.update_user_daily_selection("active_user", user_data)

    mock_update.assert_called_once_with("active_user", user_data)


def test_remove_word_completely_success(rune_recall_service, state_manager):
    """Test successful complete word removal."""
    from unittest.mock import MagicMock, patch

    from src.runestone.state.state_types import WordOfDay

    # Setup user data
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter")]
    user_data.db_user_id = 1

    # Mock vocabulary repository responses
    mock_word = MagicMock(id=1, word_phrase="kontanter")

    with (
        patch.object(
            rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=mock_word
        ),
        patch.object(
            rune_recall_service.vocabulary_repository, "delete_vocabulary_item_by_word_phrase", return_value=True
        ),
    ):

        result = rune_recall_service.remove_word_completely("active_user", "kontanter")

        assert result["success"] is True
        assert "kontanter" in result["message"]
        assert "removed from vocabulary" in result["message"]
        assert result["removed_from_selection"] is True

        # Verify repository calls
        rune_recall_service.vocabulary_repository.get_vocabulary_item_by_word_phrase.assert_called_once_with(
            "kontanter", 1
        )
        rune_recall_service.vocabulary_repository.delete_vocabulary_item_by_word_phrase.assert_called_once_with(
            "kontanter", 1
        )


def test_remove_word_completely_word_not_found(rune_recall_service, state_manager):
    """Test complete word removal when word is not found."""
    from unittest.mock import patch

    user_data = state_manager.get_user("active_user")
    user_data.db_user_id = 1

    # Mock vocabulary repository to return None (word not found)
    with patch.object(
        rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=None
    ):
        result = rune_recall_service.remove_word_completely("active_user", "nonexistent")

        assert result["success"] is False
        assert "not found in your vocabulary" in result["message"]


def test_remove_word_completely_db_failure(rune_recall_service, state_manager):
    """Test complete word removal when database deletion fails."""
    from unittest.mock import MagicMock, patch

    user_data = state_manager.get_user("active_user")
    user_data.db_user_id = 1

    # Mock vocabulary repository responses
    mock_word = MagicMock(id=1, word_phrase="kontanter")

    with (
        patch.object(
            rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=mock_word
        ),
        patch.object(
            rune_recall_service.vocabulary_repository, "delete_vocabulary_item_by_word_phrase", return_value=False
        ),
    ):

        result = rune_recall_service.remove_word_completely("active_user", "kontanter")

        assert result["success"] is False
        assert "Failed to remove word" in result["message"]


def test_remove_word_completely_user_not_found(rune_recall_service, state_manager):
    """Test complete word removal when user is not found."""
    result = rune_recall_service.remove_word_completely("nonexistent_user", "kontanter")

    assert result["success"] is False
    assert "User 'nonexistent_user' not found" in result["message"]


def test_postpone_word_success(rune_recall_service, state_manager):
    """Test successful word postponement."""
    from src.runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter"), WordOfDay(id_=2, word_phrase="hej")]

    result = rune_recall_service.postpone_word("active_user", "kontanter")

    assert result["success"] is True
    assert "postponed" in result["message"]
    assert "kontanter" in result["message"]


def test_postpone_word_not_in_selection(rune_recall_service, state_manager):
    """Test postponing word that's not in daily selection."""
    from src.runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="hej")]

    result = rune_recall_service.postpone_word("active_user", "kontanter")

    assert result["success"] is False
    assert "was not in today's selection" in result["message"]


def test_postpone_word_user_not_found(rune_recall_service, state_manager):
    """Test postponing word when user is not found."""
    result = rune_recall_service.postpone_word("nonexistent_user", "kontanter")

    assert result["success"] is False


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_with_special_characters(mock_client_class, rune_recall_service):
    """Test that special Markdown characters in translation and example are properly escaped."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Word with special characters that need escaping
    word = {
        "id": 1,
        "word_phrase": "vindruvor",
        "translation": "(-r, -de, -t) grapes",
        "example_phrase": "vindruvor _ kr/kilo",
    }

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    # Check that the message contains escaped characters
    expected_message = (
        "🇸🇪 **vindruvor**\n" "🇬🇧 \\(\\-r, \\-de, \\-t\\) grapes\n" "\n" "💡 *Example:* vindruvor \\_ kr/kilo"
    )
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "Markdown"},
    )


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_escapes_all_markdown_chars(mock_client_class, rune_recall_service):
    """Test that all Markdown special characters are properly escaped."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Word with various special characters
    word = {
        "id": 1,
        "word_phrase": "test",
        "translation": (
            "*bold* _italic_ [link](url) `code` > quote # header + list - item | table {code} .period !exclamation"
        ),
        "example_phrase": "~strikethrough~ =underline= (parentheses) [brackets]",
    }

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    # Check that all special characters are escaped
    expected_message = (
        "🇸🇪 **test**\n"
        "🇬🇧 \\*bold\\* \\_italic\\_ \\[link\\]\\(url\\) \\`code\\` \\> quote \\# header \\+ list \\- item \\| table \\{code\\} \\.period \\!exclamation\n" +
        ""
        "\n"
        "💡 *Example:* \\~strikethrough\\~ \\=underline\\= \\(parentheses\\) \\[brackets\\]"
    )
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "Markdown"},
    )
