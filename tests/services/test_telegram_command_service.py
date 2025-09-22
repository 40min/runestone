import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.runestone.services.telegram_command_service import TelegramCommandService
from src.runestone.state.state_manager import StateManager


@pytest.fixture
def temp_state_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        default_state = {
            "update_offset": 0,
            "users": {"authorized_user": {"db_user_id": 1, "chat_id": None, "is_active": False, "daily_selection": {}}},
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
def telegram_service(state_manager):
    return TelegramCommandService(state_manager, bot_token="test_token")


def test_init_with_token(state_manager):
    service = TelegramCommandService(state_manager, bot_token="test_token")
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"


def test_init_without_token(state_manager):
    with patch("src.runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "config_token"
        service = TelegramCommandService(state_manager)
        assert service.bot_token == "config_token"


def test_init_no_token_raises_error(state_manager):
    with patch("src.runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        with pytest.raises(ValueError, match="Telegram bot token is required"):
            TelegramCommandService(state_manager)


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
        "authorized_user", {"db_user_id": 1, "chat_id": 123, "is_active": True, "daily_selection": {}}
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
