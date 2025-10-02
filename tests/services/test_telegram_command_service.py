import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.runestone.services.rune_recall_service import RuneRecallService
from src.runestone.services.telegram_command_service import TelegramCommandService
from src.runestone.state.state_manager import StateManager
from src.runestone.state.state_types import WordOfDay


@pytest.fixture
def temp_state_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        default_state = {
            "users": {"authorized_user": {"db_user_id": 1, "chat_id": None, "is_active": False, "daily_selection": []}},
        }
        json.dump(default_state, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def state_manager(temp_state_file):
    StateManager._reset_for_testing()
    manager = StateManager(temp_state_file)
    # Ensure offset starts at 0 for each test
    manager.set_update_offset(0)
    return manager


@pytest.fixture
def mock_rune_recall_service():
    service = MagicMock(spec=RuneRecallService)
    return service


@pytest.fixture
def telegram_service(state_manager, mock_rune_recall_service):
    with patch("src.runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test_token"
        return TelegramCommandService(state_manager, mock_rune_recall_service)


@pytest.fixture
def telegram_service_with_deps(state_manager, mock_rune_recall_service):
    return TelegramCommandService(
        state_manager,
        rune_recall_service=mock_rune_recall_service,
    )


@patch("src.runestone.services.telegram_command_service.settings")
def test_init_with_token(mock_settings, state_manager, mock_rune_recall_service):
    mock_settings.telegram_bot_token = "test_token"
    service = TelegramCommandService(state_manager, mock_rune_recall_service)
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"


def test_init_without_token(state_manager, mock_rune_recall_service):
    with patch("src.runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "config_token"
        service = TelegramCommandService(state_manager, mock_rune_recall_service)
        assert service.bot_token == "config_token"


def test_init_no_token_raises_error(state_manager, mock_rune_recall_service):
    with patch("src.runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        with pytest.raises(ValueError, match="Telegram bot token is required"):
            TelegramCommandService(state_manager, mock_rune_recall_service)


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_send_message_success(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    result = telegram_service._send_message(123, "test message")
    assert result is True
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage", json={"chat_id": 123, "text": "test message"}
    )


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_send_message_failure(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.RequestError("Network error")
    mock_client_class.return_value.__enter__.return_value = mock_client

    result = telegram_service._send_message(123, "test message")
    assert result is False


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_authorized_start(mock_client_class, telegram_service, state_manager):
    mock_client = MagicMock()

    # Mock getUpdates response
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service.process_updates()

    # Check state updated
    user_data = state_manager.get_user("authorized_user")
    assert user_data.is_active is True
    assert user_data.chat_id == 123

    # Check offset updated
    assert state_manager.get_update_offset() == 2

    # Check message sent
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": "Bot started! You will receive daily vocabulary words."},
    )


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_authorized_stop(mock_client_class, telegram_service, state_manager):
    # First activate user
    state_manager.update_user(
        "authorized_user", {"db_user_id": 1, "chat_id": 123, "is_active": True, "daily_selection": []}
    )

    mock_client = MagicMock()

    # Mock getUpdates response
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 2,
                "message": {
                    "message_id": 2,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/stop",
                    "entities": [{"offset": 0, "length": 5, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service.process_updates()

    # Check state updated
    user_data = state_manager.get_user("authorized_user")
    assert user_data.is_active is False

    # Check offset updated
    assert state_manager.get_update_offset() == 3

    # Check message sent
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": "Bot stopped. You will no longer receive vocabulary words."},
    )


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_unauthorized(mock_client_class, telegram_service):
    mock_client = MagicMock()

    # Mock getUpdates response
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 3,
                "message": {
                    "message_id": 3,
                    "from": {"username": "unauthorized_user"},
                    "chat": {"id": 456},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service.process_updates()

    # Check rejection message sent
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 456, "text": "Sorry, you are not authorized to use this bot."},
    )


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_api_error(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.RequestError("API error")
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Should not raise exception, just log
    telegram_service.process_updates()

    mock_client.get.assert_called_once()


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_invalid_response(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {"ok": False, "error": "test error"}
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service.process_updates()

    mock_client.get.assert_called_once()


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_empty_updates(mock_client_class, telegram_service, state_manager):
    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {"ok": True, "result": []}
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    initial_offset = state_manager.get_update_offset()
    telegram_service.process_updates()

    # Offset should not change
    assert state_manager.get_update_offset() == initial_offset


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_non_bot_command_ignored(mock_client_class, telegram_service, state_manager):
    mock_client = MagicMock()

    # Mock getUpdates response with a message that is not a bot command
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 4,
                "message": {
                    "message_id": 4,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "Hello bot",  # Not a command
                    "entities": [],  # No entities
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response (should not be called)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service.process_updates()

    # Check offset updated
    assert state_manager.get_update_offset() == 5

    # Check no message sent (since it's not a bot command)
    mock_client.post.assert_not_called()

    # Check state not updated
    user_data = state_manager.get_user("authorized_user")
    assert user_data.is_active is False  # Should remain inactive


# Test the new text parsing function
def test_parse_word_from_reply_text(telegram_service):
    # Test successful parsing
    reply_text = "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"
    result = telegram_service._parse_word_from_reply_text(reply_text)
    assert result == "kontanter"

    # Test with bold formatting
    reply_text_with_bold = "🇸🇪 **kontanter**\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"
    result = telegram_service._parse_word_from_reply_text(reply_text_with_bold)
    assert result == "kontanter"

    # Test edge cases
    assert telegram_service._parse_word_from_reply_text("") is None
    assert telegram_service._parse_word_from_reply_text(None) is None
    assert telegram_service._parse_word_from_reply_text("🇬🇧 cash\nNo Swedish word") is None

    # Test with extra spaces
    reply_text_spaces = "🇸🇪   hej  \n🇬🇧 hello"
    result = telegram_service._parse_word_from_reply_text(reply_text_spaces)
    assert result == "hej"


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_handle_remove_command_success(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test successful /remove command"""
    # Mock RuneRecallService response
    mock_rune_recall_service.remove_word_completely.return_value = {
        "success": True,
        "message": "Word 'kontanter' removed from vocabulary and daily selection.",
        "removed_from_selection": True,
    }

    # Mock HTTP client for sending response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Create mock message with reply
    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"}}

    telegram_service_with_deps._handle_remove_command(message, "authorized_user", None, 123)

    # Verify RuneRecallService method called
    mock_rune_recall_service.remove_word_completely.assert_called_once_with("authorized_user", "kontanter")

    # Verify success message sent
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    assert "kontanter" in call_args["text"]
    assert "removed from vocabulary and daily selection" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_handle_remove_command_no_reply(mock_client_class, telegram_service_with_deps, state_manager):
    """Test /remove command without reply message"""
    user_data = state_manager.get_user("authorized_user")

    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    message = {}  # No reply_to_message

    telegram_service_with_deps._handle_remove_command(message, "authorized_user", user_data, 123)

    # Should send instruction message
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    assert "reply to a word message" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_handle_remove_command_word_not_found(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test /remove command when word is not found in database"""
    # Mock RuneRecallService response (word not found)
    mock_rune_recall_service.remove_word_completely.return_value = {
        "success": False,
        "message": "Word 'nonexistent' not found in your vocabulary",
    }

    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 nonexistent\n🇬🇧 word"}}

    telegram_service_with_deps._handle_remove_command(message, "authorized_user", None, 123)

    # Should send not found message
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    assert "not found" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_handle_postpone_command_success(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test successful /postpone command"""
    # Mock RuneRecallService response
    mock_rune_recall_service.postpone_word.return_value = {
        "success": True,
        "message": "Word 'kontanter' postponed (removed from today's selection).",
    }

    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Create mock message with reply
    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"}}

    telegram_service_with_deps._handle_postpone_command(message, "authorized_user", None, 123)

    # Verify RuneRecallService method called
    mock_rune_recall_service.postpone_word.assert_called_once_with("authorized_user", "kontanter")

    # Verify success message sent
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    assert "kontanter" in call_args["text"]
    assert "postponed" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_handle_postpone_command_not_in_selection(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test /postpone command when word is not in daily selection"""
    # Mock RuneRecallService response (word not in selection)
    mock_rune_recall_service.postpone_word.return_value = {
        "success": False,
        "message": "Word 'kontanter' was not in today's selection.",
    }

    # Mock HTTP client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash"}}

    telegram_service_with_deps._handle_postpone_command(message, "authorized_user", None, 123)

    # Should send not in selection message
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    assert "not in today's selection" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_remove_command(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test processing /remove command through main update handler"""
    # Setup user state
    user_data = state_manager.get_user("authorized_user")
    user_data.is_active = True
    user_data.chat_id = 123
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter")]
    user_data.db_user_id = 1
    state_manager.update_user("authorized_user", user_data)

    # Mock RuneRecallService response
    mock_rune_recall_service.remove_word_completely.return_value = {
        "success": True,
        "message": "Word 'kontanter' removed from vocabulary and daily selection.",
        "removed_from_selection": True,
    }

    mock_client = MagicMock()

    # Mock getUpdates response with /remove command
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/remove",
                    "entities": [{"offset": 0, "length": 7, "type": "bot_command"}],
                    "reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash"},
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service_with_deps.process_updates()

    # Verify the command was processed
    mock_client.post.assert_called_once()
    mock_rune_recall_service.remove_word_completely.assert_called_once_with("authorized_user", "kontanter")


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_postpone_command(
    mock_client_class, telegram_service_with_deps, state_manager, mock_rune_recall_service
):
    """Test processing /postpone command through main update handler"""
    # Setup user state
    user_data = state_manager.get_user("authorized_user")
    user_data.is_active = True
    user_data.chat_id = 123
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter")]
    state_manager.update_user("authorized_user", user_data)

    # Mock RuneRecallService response
    mock_rune_recall_service.postpone_word.return_value = {
        "success": True,
        "message": "Word 'kontanter' postponed (removed from today's selection).",
    }

    mock_client = MagicMock()

    # Mock getUpdates response with /postpone command
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/postpone",
                    "entities": [{"offset": 0, "length": 9, "type": "bot_command"}],
                    "reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash"},
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service_with_deps.process_updates()

    # Verify the command was processed
    mock_client.post.assert_called_once()
    mock_rune_recall_service.postpone_word.assert_called_once_with("authorized_user", "kontanter")
    call_args = mock_client.post.call_args[1]["json"]
    assert "postponed" in call_args["text"]


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_single_update_error_continues_processing(mock_client_class, telegram_service, state_manager):
    """Test that an error processing one update doesn't prevent processing other updates"""
    mock_client = MagicMock()

    # Mock getUpdates response with two updates - first one will cause error, second should still process
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            },
            {
                "update_id": 2,
                "message": {
                    "message_id": 2,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/stop",
                    "entities": [{"offset": 0, "length": 5, "type": "bot_command"}],
                },
            },
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage to fail on first call but succeed on second
    mock_post_response_fail = MagicMock()
    mock_post_response_fail.raise_for_status.side_effect = httpx.RequestError("Network error")
    mock_post_response_success = MagicMock()
    mock_post_response_success.raise_for_status.return_value = None
    mock_client.post.side_effect = [mock_post_response_fail, mock_post_response_success]

    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock state_manager.get_user to work for the first call but make update_user fail for first update
    original_update_user = state_manager.update_user
    call_count = [0]

    def mock_update_user(username, user_data):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call fails
            raise Exception("State update error")
        return original_update_user(username, user_data)

    with patch.object(state_manager, "update_user", side_effect=mock_update_user):
        telegram_service.process_updates()

    # Check that offset was still updated despite first update failure
    assert state_manager.get_update_offset() == 3

    # Both send_message calls should have been attempted
    assert mock_client.post.call_count == 2


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_fetch_updates_state_manager_error(mock_client_class, telegram_service, state_manager):
    """Test that _fetch_updates handles state manager errors gracefully"""
    # Mock state_manager.get_update_offset to raise an error
    with patch.object(state_manager, "get_update_offset", side_effect=Exception("State error")):
        telegram_service.process_updates()

    # Should not have made any HTTP requests
    mock_client_class.assert_not_called()


def test_process_single_update_handles_malformed_update(telegram_service):
    """Test that _process_single_update handles malformed updates gracefully"""
    malformed_updates = [
        {},  # Empty update
        {"update_id": 1},  # No message
        {"update_id": 2, "message": {}},  # Empty message
        {"update_id": 3, "message": {"from": {}}},  # Missing chat
        {"update_id": 4, "message": {"chat": {"id": 123}}},  # Missing from
    ]

    for update in malformed_updates:
        # Should not raise exception
        telegram_service._process_single_update(update)


def test_handle_authorized_user_command_unknown_command(telegram_service):
    """Test that unknown commands are handled gracefully"""
    user_data = MagicMock()
    user_data.is_active = True

    # Should not raise exception for unknown command
    telegram_service._handle_authorized_user_command("/unknown", {}, "test_user", user_data, 123)


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_offset_update_error(mock_client_class, telegram_service, state_manager):
    """Test that offset update errors are handled gracefully"""
    mock_client = MagicMock()

    # Mock successful getUpdates response
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock state_manager.set_update_offset to raise an error
    with patch.object(state_manager, "set_update_offset", side_effect=Exception("Offset update error")):
        # Should not raise exception, just log the error
        telegram_service.process_updates()

    # Update should still have been processed successfully
    mock_client.post.assert_called_once()

    # Update should still have been processed successfully
    mock_client.post.assert_called_once()


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_state_command_active_with_words(mock_client_class, telegram_service_with_deps, state_manager):
    """Test processing /state command for active user with daily selection"""
    # Setup user state
    user_data = state_manager.get_user("authorized_user")
    user_data.is_active = True
    user_data.chat_id = 123
    user_data.daily_selection = [WordOfDay(id_=1, word_phrase="kontanter"), WordOfDay(id_=2, word_phrase="biljett")]
    state_manager.update_user("authorized_user", user_data)

    mock_client = MagicMock()

    # Mock getUpdates response with /state command
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/state",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service_with_deps.process_updates()

    # Verify the command was processed
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    expected_text = (
        "**Current State**\n\n" "**Is Active:** ✅ Yes\n\n" "**Daily Selection:**\n" "- kontanter\n" "- biljett"
    )
    assert call_args["text"] == expected_text
    assert call_args["parse_mode"] == "MarkdownV2"


@patch("src.runestone.services.telegram_command_service.httpx.Client")
def test_process_updates_state_command_inactive_no_words(mock_client_class, telegram_service_with_deps, state_manager):
    """Test processing /state command for inactive user with no daily selection"""
    # Setup user state
    user_data = state_manager.get_user("authorized_user")
    user_data.is_active = False
    user_data.chat_id = 123
    user_data.daily_selection = []
    state_manager.update_user("authorized_user", user_data)

    mock_client = MagicMock()

    # Mock getUpdates response with /state command
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"username": "authorized_user"},
                    "chat": {"id": 123},
                    "text": "/state",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_get_response

    # Mock sendMessage response
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_post_response

    mock_client_class.return_value.__enter__.return_value = mock_client

    telegram_service_with_deps.process_updates()

    # Verify the command was processed
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args[1]["json"]
    expected_text = (
        "**Current State**\n\n" "**Is Active:** ❌ No\n\n" "**Daily Selection:**\n" "No words selected for today."
    )
    assert call_args["text"] == expected_text
    assert call_args["parse_mode"] == "MarkdownV2"
