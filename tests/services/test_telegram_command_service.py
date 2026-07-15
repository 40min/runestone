from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import httpx
import pytest

from runestone.core.exceptions import (
    RecallOperationError,
    TelegramUsernameConflictError,
    WordNotFoundError,
    WordNotInSelectionError,
)
from runestone.db.models import User
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.services.recall_service import RecallService
from runestone.services.recall_types import RecallEnableResult, RecallEnableStatus, RecallQueueWord, RecallState
from runestone.services.telegram_command_service import TelegramCommandService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService
from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore
from runestone.utils.markdown import escape_markdown


def make_state(
    *,
    user_id: int = 1,
    username: str = "authorized_user",
    chat_id: int | None = None,
    is_enabled: bool = False,
    daily_selection: list[RecallQueueWord] | None = None,
) -> RecallState:
    return RecallState(
        user_id=user_id,
        telegram_username=username,
        telegram_chat_id=chat_id,
        is_enabled=is_enabled,
        daily_selection=daily_selection or [],
    )


def make_word(word_id: int, word_phrase: str) -> RecallQueueWord:
    return RecallQueueWord(id=word_id, word_phrase=word_phrase)


def make_enable_result(
    *,
    status: RecallEnableStatus = RecallEnableStatus.ENABLED,
    username: str = "authorized_user",
    user_id: int | None = 1,
    state: RecallState | None = None,
    was_already_enabled: bool = False,
) -> RecallEnableResult:
    return RecallEnableResult(
        status=status,
        normalized_username=username,
        user_id=user_id,
        state=state,
        was_already_enabled=was_already_enabled,
    )


@pytest.fixture
def offset_store(tmp_path):
    store = TelegramUpdateOffsetStore(str(tmp_path / "offset.txt"))
    store.set_update_offset(0)
    return store


@pytest.fixture
def mock_recall_service():
    service = Mock()
    service.get_state_for_telegram_username = AsyncMock(return_value=(None, None))
    service.enable_for_username = AsyncMock(
        return_value=make_enable_result(
            status=RecallEnableStatus.USER_NOT_FOUND,
            username="unknown",
            user_id=None,
        )
    )
    service.disable_for_user = AsyncMock()
    service.remove_word_completely = AsyncMock()
    service.postpone_word = AsyncMock()
    service.bump_words = AsyncMock()
    service.rollback_failed_operation = AsyncMock()
    return service


@pytest.fixture
def telegram_service(offset_store, mock_recall_service):
    with patch("runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test_token"
        return TelegramCommandService(offset_store, mock_recall_service)


@pytest.fixture
def telegram_service_with_deps(telegram_service):
    return telegram_service


@patch("runestone.services.telegram_command_service.settings")
async def test_init_with_token(mock_settings, offset_store, mock_recall_service):
    mock_settings.telegram_bot_token = "test_token"
    service = TelegramCommandService(offset_store, mock_recall_service)
    assert service.bot_token == "test_token"
    assert service.base_url == "https://api.telegram.org/bottest_token"


async def test_init_without_token(offset_store, mock_recall_service):
    with patch("runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "config_token"
        service = TelegramCommandService(offset_store, mock_recall_service)
        assert service.bot_token == "config_token"


async def test_init_no_token_raises_error(offset_store, mock_recall_service):
    with patch("runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        with pytest.raises(ValueError, match="Telegram bot token is required"):
            TelegramCommandService(offset_store, mock_recall_service)


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_send_message_success(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"ok": True}
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    result = await telegram_service._send_message(123, "test message")
    assert result is True
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage", json={"chat_id": 123, "text": "test message"}
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_send_message_failure(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Network error"))
    mock_client_class.return_value.__aenter__.return_value = mock_client

    result = await telegram_service._send_message(123, "test message")
    assert result is False


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_send_message_http_status_returns_false(mock_client_class, telegram_service):
    request = httpx.Request("POST", "https://api.telegram.org/sendMessage")
    http_failure = MagicMock()
    http_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error",
        request=request,
        response=httpx.Response(500, request=request),
    )
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=http_failure)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    assert await telegram_service._send_message(123, "message") is False


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_authorized_start(mock_client_class, telegram_service):
    state = make_state(is_enabled=False)
    enabled_state = make_state(chat_id=123, is_enabled=True)
    telegram_service.recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    telegram_service.recall_service.enable_for_username.return_value = make_enable_result(state=enabled_state)

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    telegram_service.recall_service.get_state_for_telegram_username.assert_not_awaited()
    telegram_service.recall_service.enable_for_username.assert_awaited_once_with("authorized_user", 123)
    assert telegram_service.offset_store.get_update_offset() == 2
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": "Bot started! You will receive daily vocabulary words."},
    )


async def test_repeated_start_refreshes_link_and_reports_already_active(telegram_service):
    first_state = make_state(chat_id=123, is_enabled=True)
    refreshed_state = make_state(chat_id=456, is_enabled=True)
    telegram_service.recall_service.enable_for_username.side_effect = [
        make_enable_result(state=first_state),
        make_enable_result(state=refreshed_state, was_already_enabled=True),
    ]
    telegram_service._send_message = AsyncMock(return_value=True)

    assert await telegram_service._try_link_user_from_profile("authorized_user", 123) is True
    assert await telegram_service._try_link_user_from_profile("authorized_user", 456) is True

    assert telegram_service.recall_service.enable_for_username.await_args_list == [
        call("authorized_user", 123),
        call("authorized_user", 456),
    ]
    assert telegram_service._send_message.await_args_list == [
        call(123, "Bot started! You will receive daily vocabulary words."),
        call(456, "Bot is already active. You will continue receiving daily vocabulary words."),
    ]


async def test_start_database_failure_recovers_notifies_and_advances_best_effort_offset(telegram_service):
    update = {
        "update_id": 7,
        "message": {
            "from": {"username": "authorized_user"},
            "chat": {"id": 123},
            "text": "/start",
            "entities": [{"type": "bot_command"}],
        },
    }
    telegram_service._fetch_updates = AsyncMock(return_value=([update], 0))
    telegram_service.recall_service.enable_for_username.side_effect = RecallOperationError("Failed to enable recall")
    telegram_service._send_message = AsyncMock(return_value=True)

    await telegram_service.process_updates()

    telegram_service.recall_service.rollback_failed_operation.assert_awaited_once_with()
    telegram_service._send_message.assert_awaited_once_with(
        123,
        "Sorry, an error occurred while processing your command.",
    )
    assert telegram_service.offset_store.get_update_offset() == 8


async def test_start_acknowledgement_failure_recovers_and_attempts_generic_error(telegram_service):
    telegram_service.recall_service.enable_for_username.return_value = make_enable_result(
        state=make_state(chat_id=123, is_enabled=True)
    )
    telegram_service._send_message = AsyncMock(side_effect=[False, True])
    update = {
        "update_id": 1,
        "message": {
            "from": {"username": "authorized_user"},
            "chat": {"id": 123},
            "text": "/start",
            "entities": [{"type": "bot_command"}],
        },
    }

    await telegram_service._process_single_update(update)

    telegram_service.recall_service.rollback_failed_operation.assert_awaited_once_with()
    assert telegram_service._send_message.await_args_list == [
        call(123, "Bot started! You will receive daily vocabulary words."),
        call(123, "Sorry, an error occurred while processing your command."),
    ]


@pytest.mark.anyio
async def test_database_failure_in_update_batch_rolls_back_before_next_update(db_session):
    user = User(
        name="Batch",
        surname="Recovery",
        email="telegram-batch-recovery@example.com",
        hashed_password="hashed",
        timezone="UTC",
        telegram_username="batch_user",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()

    domain_settings = SimpleNamespace(words_per_day=1, cooldown_days=7)
    recall_repository = RecallRepository(db_session)
    recall_service = RecallService(
        recall_repository,
        VocabularyService(VocabularyRepository(db_session), domain_settings, AsyncMock()),
        UserService(UserRepository(db_session)),
        domain_settings,
    )
    original_upsert = recall_repository.upsert_for_user
    attempts = 0

    async def fail_first_upsert(user_id: int, *, chat_id: int | None, is_enabled: bool):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            db_session.add(
                User(
                    name="Duplicate",
                    surname="Email",
                    email=user.email,
                    hashed_password="hashed",
                    timezone="UTC",
                )
            )
            await db_session.flush()
        return await original_upsert(user_id, chat_id=chat_id, is_enabled=is_enabled)

    recall_repository.upsert_for_user = fail_first_upsert
    offset_store = Mock()
    offset_store.set_update_offset = Mock()
    with patch("runestone.services.telegram_command_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test_token"
        service = TelegramCommandService(offset_store, recall_service)

    def start_update(update_id: int, chat_id: int) -> dict:
        return {
            "update_id": update_id,
            "message": {
                "from": {"username": "batch_user"},
                "chat": {"id": chat_id},
                "text": "/start",
                "entities": [{"type": "bot_command"}],
            },
        }

    service._fetch_updates = AsyncMock(return_value=([start_update(1, 123), start_update(2, 456)], 0))
    service._send_message = AsyncMock(return_value=True)

    await service.process_updates()

    assert attempts == 2
    offset_store.set_update_offset.assert_called_once_with(3)
    assert service._send_message.await_args_list == [
        call(123, "Sorry, an error occurred while processing your command."),
        call(456, "Bot started! You will receive daily vocabulary words."),
    ]
    persisted = await recall_repository.get_recall_state(user.id)
    assert persisted is not None
    assert persisted.telegram_chat_id == 456
    assert persisted.is_enabled is True


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_authorized_stop(mock_client_class, telegram_service):
    state = make_state(chat_id=123, is_enabled=True)
    telegram_service.recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    telegram_service.recall_service.disable_for_user.assert_awaited_once_with(1, chat_id=123)
    assert telegram_service.offset_store.get_update_offset() == 3
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 123, "text": "Bot stopped. You will no longer receive vocabulary words."},
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unauthorized(mock_client_class, telegram_service):
    mock_client = MagicMock()
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
                    "text": "/state",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 456, "text": "Sorry, you are not authorized to use this bot."},
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unknown_start_links_active_profile_user(
    mock_client_class, telegram_service, mock_recall_service
):
    mock_recall_service.enable_for_username.return_value = make_enable_result(
        username="someuser",
        user_id=7,
        state=make_state(user_id=7, username="someuser", chat_id=789, is_enabled=True),
    )

    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 4,
                "message": {
                    "message_id": 4,
                    "from": {"username": "SomeUser"},
                    "chat": {"id": 789},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_recall_service.enable_for_username.assert_awaited_once_with("SomeUser", 789)
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 789, "text": "Bot started! You will receive daily vocabulary words."},
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unknown_start_without_profile_link(
    mock_client_class, telegram_service, mock_recall_service
):
    mock_recall_service.enable_for_username.return_value = make_enable_result(
        status=RecallEnableStatus.USER_NOT_FOUND,
        username="missing_user",
        user_id=None,
    )
    mock_client = MagicMock()

    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 5,
                "message": {
                    "message_id": 5,
                    "from": {"username": "missing_user"},
                    "chat": {"id": 790},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    call_args = mock_client.post.call_args[1]["json"]
    assert call_args["chat_id"] == 790
    assert "Add your Telegram username in Profile" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unknown_start_inactive_profile_user(
    mock_client_class, telegram_service, mock_recall_service
):
    mock_recall_service.enable_for_username.return_value = make_enable_result(
        status=RecallEnableStatus.USER_INACTIVE,
        username="inactive_user",
        user_id=8,
    )
    mock_client = MagicMock()

    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 6,
                "message": {
                    "message_id": 6,
                    "from": {"username": "inactive_user"},
                    "chat": {"id": 791},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 791, "text": "Your Runestone account is not active. Please contact an administrator."},
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unknown_start_duplicate_profile_link(
    mock_client_class, telegram_service, mock_recall_service
):
    duplicate_error = TelegramUsernameConflictError("authorized_user")
    mock_recall_service.enable_for_username.side_effect = duplicate_error
    mock_client = MagicMock()

    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 8,
                "message": {
                    "message_id": 8,
                    "from": {"username": "duplicate_user"},
                    "chat": {"id": 793},
                    "text": "/start",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={
            "chat_id": 793,
            "text": "This Telegram username is linked to multiple Runestone accounts. "
            "Please contact an administrator.",
        },
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_unknown_command_does_not_run_profile_fallback(
    mock_client_class, telegram_service, mock_recall_service
):
    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 7,
                "message": {
                    "message_id": 7,
                    "from": {"username": "unknown_user"},
                    "chat": {"id": 792},
                    "text": "/state",
                    "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_recall_service.enable_for_username.assert_not_awaited()
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottest_token/sendMessage",
        json={"chat_id": 792, "text": "Sorry, you are not authorized to use this bot."},
    )


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_api_error(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("API error"))
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_client.get.assert_called_once()


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_invalid_response(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {"ok": False, "error": "test error"}
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    mock_client.get.assert_called_once()


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_empty_updates(mock_client_class, telegram_service):
    mock_client = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {"ok": True, "result": []}
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    initial_offset = telegram_service.offset_store.get_update_offset()
    await telegram_service.process_updates()
    assert telegram_service.offset_store.get_update_offset() == initial_offset


async def test_process_updates_sorts_an_unordered_batch_by_update_id(telegram_service):
    telegram_service._fetch_updates = AsyncMock(
        return_value=([{"update_id": 12}, {"update_id": 10}, {"update_id": 11}], 0)
    )
    processed = []

    async def record(update):
        processed.append(update["update_id"])

    telegram_service._process_single_update = AsyncMock(side_effect=record)

    await telegram_service.process_updates()

    assert processed == [10, 11, 12]
    assert telegram_service.offset_store.get_update_offset() == 13


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_non_bot_command_ignored(mock_client_class, telegram_service):
    mock_client = MagicMock()
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
                    "text": "Hello bot",
                    "entities": [],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service.process_updates()

    assert telegram_service.offset_store.get_update_offset() == 5
    mock_client.post.assert_not_called()
    telegram_service.recall_service.get_state_for_telegram_username.assert_not_awaited()


async def test_parse_word_from_reply_text(telegram_service):
    reply_text = "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"
    result = telegram_service._parse_word_from_reply_text(reply_text)
    assert result == "kontanter"

    reply_text_with_bold = "🇸🇪 **kontanter**\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"
    result = telegram_service._parse_word_from_reply_text(reply_text_with_bold)
    assert result == "kontanter"

    reply_text_with_literal_underscores = "🇸🇪 __recall_it_123_00\n🇬🇧 fixture"
    result = telegram_service._parse_word_from_reply_text(reply_text_with_literal_underscores)
    assert result == "__recall_it_123_00"

    assert telegram_service._parse_word_from_reply_text("") is None
    assert telegram_service._parse_word_from_reply_text(None) is None
    assert telegram_service._parse_word_from_reply_text("🇬🇧 cash\nNo Swedish word") is None

    reply_text_spaces = "🇸🇪   hej  \n🇬🇧 hello"
    result = telegram_service._parse_word_from_reply_text(reply_text_spaces)
    assert result == "hej"


async def test_escape_markdown_v2():
    assert escape_markdown("word_with_underscore") == r"word\_with\_underscore"
    assert escape_markdown("*bold*") == r"\*bold\*"
    assert escape_markdown("[link](url)") == r"\[link\]\(url\)"
    assert escape_markdown("~strikethrough~") == r"\~strikethrough\~"
    assert escape_markdown("`code`") == r"\`code\`"
    assert escape_markdown("> quote") == r"\> quote"
    assert escape_markdown("# header") == r"\# header"
    assert escape_markdown("+ list") == r"\+ list"
    assert escape_markdown("- item") == r"\- item"
    assert escape_markdown("= equals") == r"\= equals"
    assert escape_markdown("| table |") == r"\| table \|"
    assert escape_markdown("{code}") == r"\{code\}"
    assert escape_markdown("}") == r"\}"
    assert escape_markdown(".dot") == r"\.dot"
    assert escape_markdown("!") == r"\!"
    assert escape_markdown("normalword") == "normalword"
    assert escape_markdown("word-with*special.chars!") == r"word\-with\*special\.chars\!"


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_handle_remove_command_success(mock_client_class, telegram_service_with_deps, mock_recall_service):
    mock_recall_service.remove_word_completely.return_value = None

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"}}
    state = make_state()
    await telegram_service_with_deps._handle_remove_command(message, "authorized_user", state, 123)

    mock_recall_service.remove_word_completely.assert_called_once_with(state, "kontanter")
    call_args = mock_client.post.call_args[1]["json"]
    assert "kontanter" in call_args["text"]
    assert "removed from vocabulary" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_handle_remove_command_no_reply(mock_client_class, telegram_service_with_deps):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps._handle_remove_command({}, "authorized_user", make_state(), 123)

    call_args = mock_client.post.call_args[1]["json"]
    assert "reply to a word message" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_handle_remove_command_word_not_found(mock_client_class, telegram_service_with_deps, mock_recall_service):
    mock_recall_service.remove_word_completely.side_effect = WordNotFoundError("nonexistent", "authorized_user")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 nonexistent\n🇬🇧 word"}}
    await telegram_service_with_deps._handle_remove_command(message, "authorized_user", make_state(), 123)

    call_args = mock_client.post.call_args[1]["json"]
    assert "not found" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_handle_postpone_command_success(mock_client_class, telegram_service_with_deps, mock_recall_service):
    mock_recall_service.postpone_word.return_value = None

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash\n\n💡 Example: - Tår ni kontanter?"}}
    state = make_state()
    await telegram_service_with_deps._handle_postpone_command(message, "authorized_user", state, 123)

    mock_recall_service.postpone_word.assert_called_once_with(state, "kontanter")
    call_args = mock_client.post.call_args[1]["json"]
    assert "kontanter" in call_args["text"]
    assert "postponed" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_handle_postpone_command_not_in_selection(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    mock_recall_service.postpone_word.side_effect = WordNotInSelectionError("kontanter")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    message = {"reply_to_message": {"text": "🇸🇪 kontanter\n🇬🇧 cash"}}
    await telegram_service_with_deps._handle_postpone_command(message, "authorized_user", make_state(), 123)

    call_args = mock_client.post.call_args[1]["json"]
    assert "not in today's selection" in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_remove_command(mock_client_class, telegram_service_with_deps, mock_recall_service):
    state = make_state(chat_id=123, is_enabled=True, daily_selection=[make_word(1, "kontanter")])
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    mock_recall_service.remove_word_completely.return_value = state

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    mock_client.post.assert_called_once()
    mock_recall_service.remove_word_completely.assert_called_once_with(state, "kontanter")


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_postpone_command(mock_client_class, telegram_service_with_deps, mock_recall_service):
    state = make_state(chat_id=123, is_enabled=True, daily_selection=[make_word(1, "kontanter")])
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    mock_recall_service.postpone_word.return_value = state

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    mock_client.post.assert_called_once()
    mock_recall_service.postpone_word.assert_called_once_with(state, "kontanter")
    call_args = mock_client.post.call_args[1]["json"]
    assert "postponed" in call_args["text"]


async def test_process_updates_single_update_error_continues_processing(telegram_service):
    updates = [
        {"update_id": 1, "message": {"text": "/start"}},
        {"update_id": 2, "message": {"text": "/stop"}},
    ]

    with (
        patch.object(telegram_service, "_fetch_updates", new=AsyncMock(return_value=(updates, 0))),
        patch.object(
            telegram_service,
            "_process_single_update",
            new=AsyncMock(side_effect=[RuntimeError("boom"), None]),
        ) as mock_process_single,
    ):
        await telegram_service.process_updates()

    assert mock_process_single.await_count == 2
    telegram_service.recall_service.rollback_failed_operation.assert_awaited_once()
    assert telegram_service.offset_store.get_update_offset() == 3


async def test_fetch_updates_state_manager_error(telegram_service):
    with patch.object(telegram_service.offset_store, "get_update_offset", side_effect=Exception("State error")):
        updates, max_update_id = await telegram_service._fetch_updates()

    assert updates == []
    assert max_update_id == 0


async def test_process_single_update_handles_malformed_update(telegram_service):
    malformed_updates = [
        {},
        {"update_id": 1},
        {"update_id": 2, "message": {}},
        {"update_id": 3, "message": {"from": {}}},
        {"update_id": 4, "message": {"chat": {"id": 123}}},
    ]

    for update in malformed_updates:
        await telegram_service._process_single_update(update)


async def test_handle_authorized_user_command_unknown_command(telegram_service):
    user_data = make_state(is_enabled=True)
    await telegram_service._handle_authorized_user_command("/unknown", {}, "test_user", user_data, 123)


async def test_process_updates_offset_update_error(telegram_service, mock_recall_service):
    state = make_state(chat_id=123, is_enabled=False)
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    mock_recall_service.enable_for_username.return_value = make_enable_result(
        state=make_state(chat_id=123, is_enabled=True)
    )

    with (
        patch.object(
            telegram_service,
            "_fetch_updates",
            new=AsyncMock(
                return_value=(
                    [
                        {
                            "update_id": 1,
                            "message": {
                                "from": {"username": "authorized_user"},
                                "chat": {"id": 123},
                                "text": "/start",
                                "entities": [{"type": "bot_command"}],
                            },
                        }
                    ],
                    0,
                )
            ),
        ),
        patch.object(telegram_service.offset_store, "set_update_offset", side_effect=Exception("Offset update error")),
        patch.object(telegram_service, "_send_message", new=AsyncMock(return_value=True)) as mock_send,
    ):
        await telegram_service.process_updates()

    mock_send.assert_awaited_once()


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_state_command_active_with_words(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    state = make_state(
        chat_id=123,
        is_enabled=True,
        daily_selection=[make_word(1, "kontanter"), make_word(2, "biljett")],
    )
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    call_args = mock_client.post.call_args[1]["json"]
    expected_text = "Current State\n\n" "Is Active: ✅ Yes\n\n" "Daily Selection:\n" "- kontanter\n" "- biljett"
    assert call_args["text"] == expected_text
    assert "parse_mode" not in call_args


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_state_command_inactive_no_words(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    state = make_state(chat_id=123, is_enabled=False, daily_selection=[])
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    call_args = mock_client.post.call_args[1]["json"]
    expected_text = "Current State\n\n" "Is Active: ❌ No\n\n" "Daily Selection:\n" "No words selected for today."
    assert call_args["text"] == expected_text
    assert "parse_mode" not in call_args


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_state_command_with_special_chars(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    state = make_state(
        chat_id=123,
        is_enabled=True,
        daily_selection=[make_word(1, "word-with*dots.and!special"), make_word(2, "normal_word")],
    )
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)

    mock_client = MagicMock()
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
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    call_args = mock_client.post.call_args[1]["json"]
    expected_text = (
        "Current State\n\n"
        "Is Active: ✅ Yes\n\n"
        "Daily Selection:\n"
        "- word-with*dots.and!special\n"
        "- normal_word"
    )
    assert call_args["text"] == expected_text
    assert "parse_mode" not in call_args


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_bump_words_command_success(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    state = make_state(chat_id=123, is_enabled=True, daily_selection=[make_word(1, "old_word")])
    bumped_state = make_state(chat_id=123, is_enabled=True, daily_selection=[make_word(2, "new_word")])
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    mock_recall_service.bump_words.return_value = bumped_state

    mock_client = MagicMock()
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
                    "text": "/bump_words",
                    "entities": [{"offset": 0, "length": 11, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    mock_recall_service.bump_words.assert_called_once_with(state)
    call_args = mock_client.post.call_args[1]["json"]
    assert "Daily selection updated! Selected 1 new words for today." in call_args["text"]


@patch("runestone.services.telegram_command_service.httpx.AsyncClient")
async def test_process_updates_bump_words_command_no_words_available(
    mock_client_class, telegram_service_with_deps, mock_recall_service
):
    state = make_state(chat_id=123, is_enabled=True, daily_selection=[make_word(1, "old_word")])
    cleared_state = make_state(chat_id=123, is_enabled=True, daily_selection=[])
    mock_recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    mock_recall_service.bump_words.return_value = cleared_state

    mock_client = MagicMock()
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
                    "text": "/bump_words",
                    "entities": [{"offset": 0, "length": 11, "type": "bot_command"}],
                },
            }
        ],
    }
    mock_get_response.raise_for_status.return_value = None
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_client.post = AsyncMock(return_value=mock_post_response)
    mock_client_class.return_value.__aenter__.return_value = mock_client

    await telegram_service_with_deps.process_updates()

    mock_recall_service.bump_words.assert_called_once_with(state)
    call_args = mock_client.post.call_args[1]["json"]
    assert "Daily selection cleared. No new words available at this time." in call_args["text"]
