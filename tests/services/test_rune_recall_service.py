import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.core.exceptions import VocabularyOperationError, WordNotFoundError, WordNotInSelectionError
from runestone.db.database import Base
from runestone.db.models import Vocabulary
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.rune_recall_service import RuneRecallService
from runestone.state.state_manager import StateManager
from runestone.state.state_types import WordOfDay
from runestone.utils.markdown import escape_markdown


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
    test_db_url = "sqlite:///:memory:"
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
        # Dispose the engine to close all connections
        engine.dispose()


@pytest.fixture
def vocabulary_repository(test_db):
    """Create a VocabularyRepository instance."""
    return VocabularyRepository(test_db)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.words_per_day = 5
    settings.cooldown_days = 7
    settings.telegram_bot_token = "test_token"
    settings.recall_start_hour = 9
    settings.recall_end_hour = 22
    settings.recall_interval_minutes = 60
    return settings


@pytest.fixture
def rune_recall_service(vocabulary_repository, state_manager, mock_settings):
    return RuneRecallService(vocabulary_repository, state_manager, mock_settings)


def test_init_uses_settings_values(vocabulary_repository, state_manager, mock_settings):
    service = RuneRecallService(vocabulary_repository, state_manager, mock_settings)
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"
    assert service.words_per_day == 5
    assert service.cooldown_days == 7


def test_init_with_different_settings_values(vocabulary_repository, state_manager, mock_settings):
    mock_settings.words_per_day = 3
    mock_settings.cooldown_days = 5
    service = RuneRecallService(vocabulary_repository, state_manager, mock_settings)
    assert service.words_per_day == 3
    assert service.cooldown_days == 5


def test_init_no_token_raises_error(vocabulary_repository, state_manager, mock_settings):
    mock_settings.telegram_bot_token = None
    with pytest.raises(ValueError, match="Telegram bot token is required"):
        RuneRecallService(vocabulary_repository, state_manager, mock_settings)


def test_init_uses_config_values(vocabulary_repository, state_manager, mock_settings):
    """Test that RuneRecallService uses configuration values from settings."""
    mock_settings.telegram_bot_token = "config_token"
    mock_settings.words_per_day = 10
    mock_settings.cooldown_days = 14

    service = RuneRecallService(vocabulary_repository, state_manager, mock_settings)

    assert service.bot_token == "config_token"
    assert service.words_per_day == 10
    assert service.cooldown_days == 14


@patch("runestone.services.rune_recall_service.httpx.Client")
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
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


@patch("runestone.services.rune_recall_service.httpx.Client")
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
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


@patch("runestone.services.rune_recall_service.httpx.Client")
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
    selected_words = [w["word_phrase"] for w in words]
    assert "hello" in selected_words
    assert "goodbye" in selected_words
    assert "thank you" in selected_words


def test_select_daily_portion_with_recent_history(rune_recall_service, test_db):
    # Simulate that the first word was learned recently by setting last_learned
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    hello_word.last_learned = datetime.now() - timedelta(days=1)  # Learned yesterday
    test_db.commit()

    words = rune_recall_service._select_daily_portion(1)

    assert len(words) == 2  # Should exclude the recently learned word
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases  # Should not include recently learned word


@patch("runestone.services.rune_recall_service.httpx.Client")
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


@patch("runestone.services.rune_recall_service.httpx.Client")
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


@patch("runestone.services.rune_recall_service.httpx.Client")
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


@patch("runestone.services.rune_recall_service.httpx.Client")
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


@patch("runestone.services.rune_recall_service.datetime")
def test_send_next_recall_word_within_hours(mock_datetime, rune_recall_service):
    """Test that recall words are sent when within recall hours."""
    # Mock current time to be 10 AM
    mock_datetime.now.return_value.hour = 10

    with patch.object(rune_recall_service, "_process_user_recall_word") as mock_process:
        rune_recall_service.send_next_recall_word()

    # Should process users since we're within hours
    mock_process.assert_called()


def test_send_next_recall_word_outside_hours(rune_recall_service):
    """Test that recall words are not sent when outside recall hours."""
    with patch("runestone.services.rune_recall_service.datetime") as mock_datetime:
        # Mock current time to be 2 AM
        mock_datetime.now.return_value.hour = 2

        with patch.object(rune_recall_service, "_process_user_recall_word") as mock_process:
            rune_recall_service.send_next_recall_word()

        # Should not process users since we're outside hours
        mock_process.assert_not_called()


# Tests for cooldown functionality


def test_rune_recall_service_different_cooldown_periods(vocabulary_repository, mock_settings):
    """Test RuneRecallService with different cooldown periods."""
    state_manager = MagicMock()

    # Test default cooldown (7 days)
    service_default = RuneRecallService(vocabulary_repository, state_manager, mock_settings)
    assert service_default.cooldown_days == 7

    # Test custom cooldown via settings
    mock_settings.cooldown_days = 3
    service_custom = RuneRecallService(vocabulary_repository, state_manager, mock_settings)
    assert service_custom.cooldown_days == 3

    # Test zero cooldown (should allow immediate repetition)
    mock_settings.cooldown_days = 0
    service_zero = RuneRecallService(vocabulary_repository, state_manager, mock_settings)
    assert service_zero.cooldown_days == 0


def test_select_daily_portion_different_cooldown_periods(test_db, mock_settings):
    """Test daily portion selection with different cooldown periods."""
    # Create VocabularyRepository and services with different cooldown periods
    vocabulary_repository = VocabularyRepository(test_db)
    state_manager = MagicMock()
    mock_settings.cooldown_days = 3
    service = RuneRecallService(vocabulary_repository, state_manager, mock_settings)

    # Set up test data: word learned 2 days ago
    hello_word = test_db.query(Vocabulary).filter(Vocabulary.word_phrase == "hello").first()
    hello_word.last_learned = datetime.now() - timedelta(days=2)
    test_db.commit()

    # With 3-day cooldown, word should be excluded
    words = service._select_daily_portion(1)
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases

    # Create service with 1-day cooldown
    mock_settings.cooldown_days = 1
    service_short = RuneRecallService(vocabulary_repository, state_manager, mock_settings)

    # With 1-day cooldown, word should be included
    words = service_short._select_daily_portion(1)
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" in word_phrases


@patch("runestone.services.rune_recall_service.httpx.Client")
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


def test_select_daily_portion_words_per_day_limit(test_db, mock_settings):
    """Test that daily portion respects words_per_day limit."""
    # Create service with limit of 2 words per day
    vocabulary_repository = VocabularyRepository(test_db)
    state_manager = MagicMock()
    mock_settings.words_per_day = 2
    service = RuneRecallService(vocabulary_repository, state_manager, mock_settings)

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
    from runestone.state.state_types import WordOfDay

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


def test_maintain_daily_selection_adds_words_when_below_target(rune_recall_service, state_manager):
    """Test maintaining daily_selection when below target count."""
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = []
    user_data.db_user_id = 1

    # Mock vocabulary repository to return new words
    from runestone.db.models import Vocabulary

    mock_words = [
        Vocabulary(id=4, word_phrase="ny", translation="new", example_phrase="", in_learn=True, user_id=1),
        Vocabulary(id=5, word_phrase="gammal", translation="old", example_phrase="", in_learn=True, user_id=1),
    ]

    with patch.object(rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=mock_words):
        added_count = rune_recall_service.maintain_daily_selection("active_user", user_data)

    assert added_count == 2
    assert len(user_data.daily_selection) == 2
    assert user_data.daily_selection[0].id_ == 4
    assert user_data.daily_selection[0].word_phrase == "ny"


def test_maintain_daily_selection_not_needed_when_at_target(rune_recall_service, state_manager):
    """Test that maintenance doesn't happen when selection is already at target."""
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    # Set selection to target count (5 words per day based on mock_settings)
    user_data.daily_selection = [
        WordOfDay(id_=1, word_phrase="word1"),
        WordOfDay(id_=2, word_phrase="word2"),
        WordOfDay(id_=3, word_phrase="word3"),
        WordOfDay(id_=4, word_phrase="word4"),
        WordOfDay(id_=5, word_phrase="word5"),
    ]

    with patch.object(rune_recall_service.vocabulary_repository, "select_new_daily_words") as mock_select:
        added_count = rune_recall_service.maintain_daily_selection("active_user", user_data)

    # Should not call repository since we're at target
    mock_select.assert_not_called()
    assert added_count == 0
    assert len(user_data.daily_selection) == 5


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
    """Test successful complete word removal with automatic replacement."""
    from unittest.mock import MagicMock, patch

    from src.runestone.db.models import Vocabulary
    from src.runestone.state.state_types import WordOfDay

    # Setup user data with one word (below target of 5)
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter")]
    user_data.db_user_id = 1

    # Mock vocabulary repository responses
    mock_word = MagicMock(id=1, word_phrase="kontanter")
    mock_replacement = Vocabulary(
        id=10, word_phrase="replacement", translation="repl", example_phrase="", in_learn=True, user_id=1
    )

    with (
        patch.object(
            rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=mock_word
        ),
        patch.object(
            rune_recall_service.vocabulary_repository, "delete_vocabulary_item_by_word_phrase", return_value=True
        ),
        patch.object(
            rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=[mock_replacement]
        ),
    ):

        # Success case - no exception raised
        rune_recall_service.remove_word_completely("active_user", "kontanter")

        # Verify repository calls
        rune_recall_service.vocabulary_repository.get_vocabulary_item_by_word_phrase.assert_called_once_with(
            "kontanter", 1
        )
        rune_recall_service.vocabulary_repository.delete_vocabulary_item_by_word_phrase.assert_called_once_with(
            "kontanter", 1
        )
        # Verify replacement was requested (excluding the removed word's ID)
        rune_recall_service.vocabulary_repository.select_new_daily_words.assert_called_once()


def test_remove_word_completely_word_not_found(rune_recall_service, state_manager):
    """Test complete word removal when word is not found."""
    from unittest.mock import patch

    user_data = state_manager.get_user("active_user")
    user_data.db_user_id = 1

    # Mock vocabulary repository to return None (word not found)
    with patch.object(
        rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=None
    ):
        with pytest.raises(WordNotFoundError) as exc_info:
            rune_recall_service.remove_word_completely("active_user", "nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


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

        with pytest.raises(VocabularyOperationError) as exc_info:
            rune_recall_service.remove_word_completely("active_user", "kontanter")

        assert "Failed to remove word" in str(exc_info.value)


def test_remove_word_completely_user_not_found(rune_recall_service, state_manager):
    """Test complete word removal when user is not found."""
    with pytest.raises(VocabularyOperationError) as exc_info:
        rune_recall_service.remove_word_completely("nonexistent_user", "kontanter")

    assert "nonexistent_user" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_postpone_word_success(rune_recall_service, state_manager):
    """Test successful word postponement with automatic replacement."""
    from unittest.mock import patch

    from runestone.db.models import Vocabulary
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter"), WordOfDay(id_=2, word_phrase="hej")]
    user_data.db_user_id = 1

    # Mock replacement word
    mock_replacement = Vocabulary(
        id=10, word_phrase="replacement", translation="repl", example_phrase="", in_learn=True, user_id=1
    )

    with patch.object(
        rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=[mock_replacement]
    ):
        # Success case - no exception raised
        rune_recall_service.postpone_word("active_user", "kontanter")


def test_postpone_word_not_in_selection(rune_recall_service, state_manager):
    """Test postponing word that's not in daily selection."""
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="hej")]

    with pytest.raises(WordNotInSelectionError) as exc_info:
        rune_recall_service.postpone_word("active_user", "kontanter")

    assert "kontanter" in str(exc_info.value)
    assert "not in today's selection" in str(exc_info.value)


def test_postpone_word_user_not_found(rune_recall_service, state_manager):
    """Test postponing word when user is not found."""
    with pytest.raises(VocabularyOperationError) as exc_info:
        rune_recall_service.postpone_word("nonexistent_user", "kontanter")

    assert "nonexistent_user" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


@patch("runestone.services.rune_recall_service.httpx.Client")
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
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


@patch("runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_with_special_characters_in_word_phrase(mock_client_class, rune_recall_service):
    """Test that special Markdown characters in word_phrase are properly escaped."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Word with special characters in word_phrase that need escaping
    word = {
        "id": 1,
        "word_phrase": "glas (-et, -, -en)",
        "translation": "glass",
        "example_phrase": None,
    }

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    # Check that the word_phrase is properly escaped
    expected_message = "🇸🇪 **glas \\(\\-et, \\-, \\-en\\)**\n🇬🇧 glass"
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


@patch("runestone.services.rune_recall_service.httpx.Client")
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
            "*bold* _italic_ [link](url) `code` > quote # header + list - item | table {code} .period " "!exclamation"
        ),
        "example_phrase": "~strikethrough~ =underline= (parentheses) [brackets]",
    }

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    # Check that all special characters are escaped
    expected_message = (
        "🇸🇪 **test**\n"
        "🇬🇧 \\*bold\\* \\_italic\\_ \\[link\\]\\(url\\) \\`code\\` \\> quote \\# header \\+ list \\- item \\| table "
        "\\{code\\} \\.period \\!exclamation\n\n"
        "💡 *Example:* \\~strikethrough\\~ \\=underline\\= \\(parentheses\\) \\[brackets\\]"
    )
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


def test_escape_markdown_double_escaping():
    """Test that escape_markdown does double-escape already escaped characters with the new implementation."""
    # Test with already escaped characters
    text_with_escaped = "This is \\*already escaped\\* and this is *not escaped*"
    result = escape_markdown(text_with_escaped)
    expected = "This is \\\\*already escaped\\\\* and this is \\*not escaped\\*"
    assert result == expected

    # Test with mixed escaped and unescaped characters
    mixed_text = "Some \\[escaped\\] and some [unescaped] brackets"
    result = escape_markdown(mixed_text)
    expected = "Some \\\\[escaped\\\\] and some \\[unescaped\\] brackets"
    assert result == expected

    # Test with multiple escape characters
    multi_escape = "\\*bold\\* and _italic_ and \\`code\\` and `more code`"
    result = escape_markdown(multi_escape)
    expected = "\\\\*bold\\\\* and \\_italic\\_ and \\\\`code\\\\` and \\`more code\\`"
    assert result == expected


def test_escape_markdown_all_special_chars():
    """Test that all special characters are properly escaped."""
    special_chars = "*_[]()~`>#+-=|{}.!"
    result = escape_markdown(special_chars)
    expected = "\\*\\_\\[\\]\\(\\)\\~\\`\\>\\#\\+\\-\\=\\|\\{\\}\\.\\!"
    assert result == expected


def test_escape_markdown_already_fully_escaped():
    """Test that fully escaped text gets double-escaped with the new implementation."""
    fully_escaped = "\\*\\_\\[\\]\\(\\)\\~\\`\\>\\#\\+\\-\\=\\|\\{\\}\\.\\!"
    result = escape_markdown(fully_escaped)
    # With the new implementation, already escaped characters get double-escaped for safety
    expected = "\\\\*\\\\_\\\\[\\\\]\\\\(\\\\)\\\\~\\\\`\\\\>\\\\#\\\\+\\\\-\\\\=\\\\|\\\\{\\\\}\\\\.\\\\!"
    assert result == expected


def test_escape_markdown_empty_and_normal_text():
    """Test edge cases with empty strings and normal text."""
    # Empty string
    assert escape_markdown("") == ""

    # Normal text without special characters
    normal_text = "Hello world this is normal text"
    assert escape_markdown(normal_text) == normal_text

    # Text with only spaces and alphanumeric characters
    simple_text = "abc 123 def"
    assert escape_markdown(simple_text) == simple_text


def test_bump_words_success(rune_recall_service, state_manager):
    """Test successful bump_words operation."""

    # Setup user data with existing daily selection
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="old_word")]
    user_data.next_word_index = 1
    user_data.db_user_id = 1

    # Mock new portion selection
    mock_portion = [
        {"id": 2, "word_phrase": "new_word1"},
        {"id": 3, "word_phrase": "new_word2"},
    ]

    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_portion):
        # Success case - no exception raised
        rune_recall_service.bump_words("active_user", user_data)

    # Verify daily selection was replaced
    assert len(user_data.daily_selection) == 2
    assert user_data.daily_selection[0].word_phrase == "new_word1"
    assert user_data.daily_selection[1].word_phrase == "new_word2"
    assert user_data.next_word_index == 0

    # Verify state was updated
    updated_user_data = state_manager.get_user("active_user")
    assert len(updated_user_data.daily_selection) == 2


def test_bump_words_no_words_available(rune_recall_service, state_manager):
    """Test bump_words when no new words are available."""

    # Setup user data with existing daily selection
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="old_word")]
    user_data.db_user_id = 1

    # Mock empty portion selection
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=[]):
        # Success case - no exception raised
        rune_recall_service.bump_words("active_user", user_data)

    # Verify daily selection was cleared
    assert len(user_data.daily_selection) == 0
    assert user_data.next_word_index == 0

    # Verify state was updated
    updated_user_data = state_manager.get_user("active_user")
    assert len(updated_user_data.daily_selection) == 0


def test_bump_words_error_handling(rune_recall_service, state_manager):
    """Test bump_words error handling."""
    from runestone.state.state_types import WordOfDay

    # Setup user data
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="old_word")]
    user_data.db_user_id = 1

    # Mock _select_daily_portion to raise an exception
    with patch.object(rune_recall_service, "_select_daily_portion", side_effect=Exception("Database error")):
        with pytest.raises(Exception) as exc_info:
            rune_recall_service.bump_words("active_user", user_data)

    assert "Database error" in str(exc_info.value)


@patch("runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_removes_missing_word_and_retries(
    mock_client_class, rune_recall_service, state_manager, test_db
):
    """Test that missing words are removed from daily_selection and the next word is tried."""

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Setup user with daily selection containing 3 words
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [
        WordOfDay(id_=999, word_phrase="missing_word"),  # This word doesn't exist
        WordOfDay(id_=1, word_phrase="hello"),  # This exists in test_db
        WordOfDay(id_=2, word_phrase="goodbye"),
    ]
    user_data.next_word_index = 0
    user_data.chat_id = 123

    rune_recall_service._process_user_recall_word("active_user", user_data)

    # Verify the missing word was removed from daily_selection
    updated_user = state_manager.get_user("active_user")
    assert len(updated_user.daily_selection) == 2
    word_phrases = [w.word_phrase for w in updated_user.daily_selection]
    assert "missing_word" not in word_phrases
    assert "hello" in word_phrases
    assert "goodbye" in word_phrases


@patch("runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_all_words_invalid_bumps_and_retries(
    mock_client_class, rune_recall_service, state_manager, test_db
):
    """Test that when all words are invalid, bump_words is called and method retries with new selection."""

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Setup user with all invalid words
    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [
        WordOfDay(id_=999, word_phrase="missing1"),
        WordOfDay(id_=998, word_phrase="missing2"),
    ]
    user_data.next_word_index = 0
    user_data.chat_id = 123
    user_data.db_user_id = 1

    # Mock new words selection - return a valid word from test_db
    mock_new_words = [{"id": 1, "word_phrase": "hello"}]

    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_new_words):
        rune_recall_service._process_user_recall_word("active_user", user_data)

    # Verify bump_words was called by checking selection was replaced
    updated_user = state_manager.get_user("active_user")
    assert len(updated_user.daily_selection) == 1
    assert updated_user.daily_selection[0].word_phrase == "hello"

    # Verify the new word was sent (retry happened)
    mock_client.post.assert_called_once()


def test_ensure_daily_selection_creates_new_selection(rune_recall_service, state_manager):
    """Test _ensure_daily_selection creates a new selection when needed."""

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = []

    mock_words = [{"id": 1, "word_phrase": "test"}]
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=mock_words):
        result = rune_recall_service._ensure_daily_selection("active_user", user_data)

    assert result is True
    assert len(user_data.daily_selection) == 1
    assert user_data.next_word_index == 0


def test_ensure_daily_selection_returns_false_when_no_words(rune_recall_service, state_manager):
    """Test _ensure_daily_selection returns False when no words available."""
    from unittest.mock import patch

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = []

    with patch.object(rune_recall_service, "_select_daily_portion", return_value=[]):
        result = rune_recall_service._ensure_daily_selection("active_user", user_data)

    assert result is False


def test_get_next_word_id_to_send_returns_correct_id(rune_recall_service, state_manager):
    """Test _get_next_word_id_to_send returns the correct word ID."""

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="first"), WordOfDay(id_=2, word_phrase="second")]
    user_data.next_word_index = 1

    word_id = rune_recall_service._get_next_word_id_to_send(user_data)
    assert word_id == 2


def test_get_next_word_id_to_send_resets_index(rune_recall_service, state_manager):
    """Test _get_next_word_id_to_send resets index when out of bounds."""

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="first")]
    user_data.next_word_index = 5  # Out of bounds

    word_id = rune_recall_service._get_next_word_id_to_send(user_data)
    assert word_id == 1
    assert user_data.next_word_index == 0


def test_remove_word_by_id_from_selection(rune_recall_service, state_manager):
    """Test _remove_word_by_id_from_selection removes correct word."""

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [
        WordOfDay(id_=1, word_phrase="first"),
        WordOfDay(id_=2, word_phrase="second"),
        WordOfDay(id_=3, word_phrase="third"),
    ]
    user_data.next_word_index = 1

    result = rune_recall_service._remove_word_by_id_from_selection(user_data, 2)

    assert result is True
    assert len(user_data.daily_selection) == 2
    remaining_ids = [w.id_ for w in user_data.daily_selection]
    assert 2 not in remaining_ids
    assert 1 in remaining_ids
    assert 3 in remaining_ids


def test_remove_word_by_id_adjusts_index(rune_recall_service, state_manager):
    """Test _remove_word_by_id_from_selection adjusts index when needed."""

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="first")]
    user_data.next_word_index = 1  # Out of bounds after removal

    rune_recall_service._remove_word_by_id_from_selection(user_data, 1)

    assert user_data.next_word_index == 0


@patch("runestone.services.rune_recall_service.httpx.Client")
def test_send_word_message_with_user_example(mock_client_class, rune_recall_service):
    """Test the exact failing example from user: favorit with translation (-en, -er, -erna) favorite."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # The exact failing example from user
    word = {
        "id": 1,
        "word_phrase": "favorit",
        "translation": "(-en, -er, -erna) favorite",
        "example_phrase": None,
    }

    result = rune_recall_service._send_word_message(123, word)
    assert result is True

    # Check what the message looks like
    expected_message = "🇸🇪 **favorit**\n🇬🇧 \\(\\-en, \\-er, \\-erna\\) favorite"
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": expected_message, "parse_mode": "MarkdownV2"},
    )


# Tests for new word replacement functionality


def test_maintain_daily_selection_with_partial_selection(rune_recall_service, state_manager):
    """Test maintaining daily selection when partially filled."""
    from runestone.db.models import Vocabulary
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    # Start with 2 words (target is 5)
    user_data.daily_selection = [
        WordOfDay(id_=1, word_phrase="word1"),
        WordOfDay(id_=2, word_phrase="word2"),
    ]
    user_data.db_user_id = 1

    # Mock 3 replacement words
    mock_replacements = [
        Vocabulary(id=3, word_phrase="word3", translation="t3", example_phrase="", in_learn=True, user_id=1),
        Vocabulary(id=4, word_phrase="word4", translation="t4", example_phrase="", in_learn=True, user_id=1),
        Vocabulary(id=5, word_phrase="word5", translation="t5", example_phrase="", in_learn=True, user_id=1),
    ]

    with patch.object(
        rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=mock_replacements
    ) as mock_select:
        added_count = rune_recall_service.maintain_daily_selection("active_user", user_data)

    assert added_count == 3
    assert len(user_data.daily_selection) == 5
    # Verify excluded_word_ids parameter was passed correctly
    call_args = mock_select.call_args
    assert call_args.kwargs["excluded_word_ids"] == [1, 2]


def test_maintain_daily_selection_no_replacements_available(rune_recall_service, state_manager):
    """Test maintaining daily selection when no replacement words are available."""
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="word1")]
    user_data.db_user_id = 1

    # Mock no replacement words available
    with patch.object(rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=[]):
        added_count = rune_recall_service.maintain_daily_selection("active_user", user_data)

    assert added_count == 0
    assert len(user_data.daily_selection) == 1  # Still has the original word


def test_remove_word_completely_no_replacement_available(rune_recall_service, state_manager):
    """Test word removal when no replacement words are available."""
    from unittest.mock import MagicMock, patch

    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter")]
    user_data.db_user_id = 1

    mock_word = MagicMock(id=1, word_phrase="kontanter")

    with (
        patch.object(
            rune_recall_service.vocabulary_repository, "get_vocabulary_item_by_word_phrase", return_value=mock_word
        ),
        patch.object(
            rune_recall_service.vocabulary_repository, "delete_vocabulary_item_by_word_phrase", return_value=True
        ),
        patch.object(rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=[]),
    ):
        # Success case - no exception raised
        rune_recall_service.remove_word_completely("active_user", "kontanter")


def test_postpone_word_no_replacement_available(rune_recall_service, state_manager):
    """Test word postponement when no replacement words are available."""
    from unittest.mock import patch

    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter"), WordOfDay(id_=2, word_phrase="hej")]
    user_data.db_user_id = 1

    with patch.object(rune_recall_service.vocabulary_repository, "select_new_daily_words", return_value=[]):
        # Success case - no exception raised
        rune_recall_service.postpone_word("active_user", "kontanter")


def test_maintain_daily_selection_excludes_existing_words(rune_recall_service, state_manager, test_db):
    """Test that maintain_daily_selection excludes words already in selection."""
    from runestone.state.state_types import WordOfDay

    user_data = state_manager.get_user("active_user")
    user_data.daily_selection = [
        WordOfDay(id_=1, word_phrase="hello"),  # Already in selection
    ]
    user_data.db_user_id = 1

    # Ensure all words are available
    words = test_db.query(Vocabulary).filter(Vocabulary.user_id == 1).all()
    for word in words:
        word.last_learned = datetime.now() - timedelta(days=10)
    test_db.commit()

    # Call maintain to add more words
    added_count = rune_recall_service.maintain_daily_selection("active_user", user_data)

    # Should add words, but not include the one already in selection
    assert added_count > 0
    word_ids = [w.id_ for w in user_data.daily_selection]
    # Should not have duplicate of word id=1
    assert word_ids.count(1) == 1
