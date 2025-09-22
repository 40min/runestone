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
from src.runestone.services.rune_recall_service import RuneRecallService
from src.runestone.state.state_manager import StateManager


@pytest.fixture
def temp_state_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        default_state = {
            "update_offset": 0,
            "users": {
                "active_user": {"db_user_id": 1, "chat_id": 123, "is_active": True, "daily_selection": {}},
                "inactive_user": {"db_user_id": 2, "chat_id": 456, "is_active": False, "daily_selection": {}},
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
                showed_times=0,
            ),
            Vocabulary(
                user_id=1,
                word_phrase="goodbye",
                translation="hej då",
                example_phrase="Goodbye, see you later!",
                in_learn=True,
                showed_times=0,
            ),
            Vocabulary(
                user_id=1,
                word_phrase="thank you",
                translation="tack",
                example_phrase="Thank you for your help.",
                in_learn=True,
                showed_times=0,
            ),
            Vocabulary(
                user_id=2,
                word_phrase="water",
                translation="vatten",
                example_phrase="I need water.",
                in_learn=True,
                showed_times=0,
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
def rune_recall_service(state_manager):
    return RuneRecallService(state_manager, bot_token="test_token")


def test_init_with_token(state_manager):
    service = RuneRecallService(state_manager, bot_token="test_token")
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"
    assert service.words_per_day == 5
    assert service.cooldown_days == 7


def test_init_with_custom_params(state_manager):
    service = RuneRecallService(state_manager, bot_token="test_token", words_per_day=3, cooldown_days=5)
    assert service.words_per_day == 3
    assert service.cooldown_days == 5


def test_init_without_token(state_manager):
    with patch("src.runestone.services.rune_recall_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "config_token"
        service = RuneRecallService(state_manager)
        assert service.bot_token == "config_token"


def test_init_no_token_raises_error(state_manager):
    with patch("src.runestone.services.rune_recall_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        with pytest.raises(ValueError, match="Telegram bot token is required"):
            RuneRecallService(state_manager)


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

    expected_message = "📖 **hello**\n🇸🇪 hej\n\n💡 *Example:* Hello, how are you?"
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

    expected_message = "📖 **hello**\n🇸🇪 hej"
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


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_select_words_for_today(mock_client_class, mock_session_local, rune_recall_service, test_db):
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client (not used in this test)
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Test selecting words for user 1
    words = rune_recall_service._select_words_for_today(1, {})

    assert len(words) == 3  # Should select all 3 words for user 1
    assert words[0]["word_phrase"] == "hello"  # Order by ID since timestamps are identical
    assert words[1]["word_phrase"] == "goodbye"
    assert words[2]["word_phrase"] == "thank you"


@patch("src.runestone.services.rune_recall_service.SessionLocal")
def test_select_words_with_recent_history(mock_session_local, rune_recall_service, test_db):
    # Mock the database session
    mock_session_local.return_value = test_db

    # Simulate that word with id 1 was sent recently
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    daily_selection = {yesterday: [1]}  # Word ID 1 was sent yesterday

    words = rune_recall_service._select_words_for_today(1, daily_selection)

    assert len(words) == 2  # Should exclude the recently sent word
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" not in word_phrases  # Should not include recently sent word


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_daily_words_success(
    mock_client_class, mock_session_local, rune_recall_service, test_db, state_manager
):
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Process daily words for active user
    rune_recall_service._process_user_daily_words("active_user")

    # Check that state was updated with today's selection
    user_data = state_manager.get_user("active_user")
    today = datetime.now().date().isoformat()
    assert today in user_data.daily_selection
    assert len(user_data.daily_selection[today]) == 3  # All 3 words sent

    # Check that messages were sent
    assert mock_client.post.call_count == 3


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_daily_words_no_words(mock_client_class, mock_session_local, rune_recall_service, test_db):
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Process for user 2 (who has only 1 word)
    rune_recall_service._process_user_daily_words("inactive_user")

    # Should not send any messages since user is inactive
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_missing_data(mock_client_class, rune_recall_service, state_manager):
    # Mock HTTP client
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Update existing user to have missing chat_id
    state_manager.update_user(
        "active_user", {"db_user_id": 1, "chat_id": None, "is_active": True, "daily_selection": {}}
    )

    rune_recall_service._process_user_daily_words("active_user")

    # Should not send any messages
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_daily_words_multiple_users(mock_client_class, rune_recall_service, state_manager):
    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock the word selection to return empty (to avoid database dependency)
    with patch.object(rune_recall_service, "_select_daily_portion", return_value=[]):
        rune_recall_service.send_daily_words()

    # Should not send any messages since no words selected
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_send_daily_words_with_errors(mock_client_class, rune_recall_service, state_manager):
    # Mock HTTP client to fail
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Network error")
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock word selection to return some words
    mock_words = [{"id": 1, "word_phrase": "test", "translation": "test", "example_phrase": None}]

    with patch.object(rune_recall_service, "_select_words_for_today", return_value=mock_words):
        # Should not raise exception, just log errors
        rune_recall_service._process_user_daily_words("active_user")

    # Should have attempted to send message despite error
    mock_client.post.assert_called_once()


def test_daily_selection_cleanup(rune_recall_service, state_manager):
    """Test that old daily selection entries are cleaned up."""
    # Add user with old daily selection data
    old_date = (datetime.now() - timedelta(days=40)).date().isoformat()
    recent_date = (datetime.now() - timedelta(days=5)).date().isoformat()

    state_manager.update_user(
        "active_user",
        {
            "db_user_id": 1,
            "chat_id": 123,
            "is_active": True,
            "daily_selection": {old_date: [1, 2], recent_date: [3, 4]},  # Should be cleaned up  # Should be kept
        },
    )

    # Mock word selection and message sending
    mock_words = [{"id": 5, "word_phrase": "new", "translation": "new", "example_phrase": None}]

    with (
        patch.object(rune_recall_service, "_select_words_for_today", return_value=mock_words),
        patch.object(rune_recall_service, "_send_word_message", return_value=True),
    ):

        rune_recall_service._process_user_daily_words("active_user")

    # Check that old entries were cleaned up
    user_data = state_manager.get_user("active_user")
    assert old_date not in user_data.daily_selection
    assert recent_date in user_data.daily_selection


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


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_new_portion(
    mock_client_class, mock_session_local, rune_recall_service, test_db, state_manager
):
    """Test processing recall word when selecting new daily portion."""
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Process recall word for active user (no existing portion)
    rune_recall_service._process_user_recall_word("active_user")

    # Check that daily selection was created
    user_data = state_manager.get_user("active_user")
    today = datetime.now().date().isoformat()
    assert today in user_data.daily_selection
    assert len(user_data.daily_selection[today]) == 3  # All 3 word IDs
    assert user_data.next_word_index == 1  # First word sent

    # Check that message was sent
    mock_client.post.assert_called_once()


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_existing_portion(
    mock_client_class, mock_session_local, rune_recall_service, test_db, state_manager
):
    """Test processing recall word with existing daily portion."""
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client for successful message sending
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Set up existing selection with next_word_index = 1
    today = datetime.now().date().isoformat()

    state_manager.update_user(
        "active_user",
        {
            "db_user_id": 1,
            "chat_id": 123,
            "is_active": True,
            "daily_selection": {today: [1, 2, 3]},
            "next_word_index": 1,
        },
    )

    # Process recall word
    rune_recall_service._process_user_recall_word("active_user")

    # Check that next word was sent (index 1 -> 2)
    user_data = state_manager.get_user("active_user")
    assert user_data.next_word_index == 2

    # Check that message was sent
    mock_client.post.assert_called_once()


@patch("src.runestone.services.rune_recall_service.SessionLocal")
@patch("src.runestone.services.rune_recall_service.httpx.Client")
def test_process_user_recall_word_all_sent(
    mock_client_class, mock_session_local, rune_recall_service, test_db, state_manager
):
    """Test processing recall word when all words in portion are sent."""
    # Mock the database session
    mock_session_local.return_value = test_db

    # Mock HTTP client
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Set up selection with all words sent
    today = datetime.now().date().isoformat()

    state_manager.update_user(
        "active_user",
        {
            "db_user_id": 1,
            "chat_id": 123,
            "is_active": True,
            "daily_selection": {today: [1]},
            "next_word_index": 1,  # All words sent
        },
    )

    # Process recall word
    rune_recall_service._process_user_recall_word("active_user")

    # Should not send any messages
    mock_client.post.assert_not_called()


@patch("src.runestone.services.rune_recall_service.SessionLocal")
def test_select_daily_portion(mock_session_local, rune_recall_service, test_db):
    """Test selecting daily portion of words."""
    # Mock the database session
    mock_session_local.return_value = test_db

    # Test selecting portion for user 1
    portion = rune_recall_service._select_daily_portion(1, {})

    assert len(portion) == 3  # Should select all 3 words for user 1
    assert portion[0]["word_phrase"] == "hello"
    assert portion[1]["word_phrase"] == "goodbye"
    assert portion[2]["word_phrase"] == "thank you"


@patch("src.runestone.services.rune_recall_service.SessionLocal")
def test_select_daily_portion_with_recent_history(mock_session_local, rune_recall_service, test_db):
    """Test selecting daily portion with recent word history."""
    # Mock the database session
    mock_session_local.return_value = test_db

    # Simulate that word with id 1 was sent recently
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    daily_selection = {yesterday: [1]}  # Word ID 1 was sent yesterday

    portion = rune_recall_service._select_daily_portion(1, daily_selection)

    assert len(portion) == 2  # Should exclude the recently sent word
    word_phrases = [w["word_phrase"] for w in portion]
    assert "hello" not in word_phrases  # Should not include recently sent word
