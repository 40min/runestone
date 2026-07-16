from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from runestone.core.exceptions import (
    RecallOperationError,
    TelegramUsernameConflictError,
    WordNotFoundError,
    WordNotInSelectionError,
)
from runestone.recall.providers import provide_recall_transaction
from runestone.recall.types import RecallEnableResult, RecallEnableStatus, RecallQueueWord, RecallState
from runestone.telegram.commands import CommandOutcome, TelegramCommandProcessor, TelegramMessage


def make_state(
    *,
    enabled: bool = True,
    chat_id: int | None = 123,
    words: list[RecallQueueWord] | None = None,
) -> RecallState:
    return RecallState(
        user_id=1,
        telegram_username="authorized_user",
        telegram_chat_id=chat_id,
        is_enabled=enabled,
        daily_selection=words or [],
    )


def command_update(update_id: int, text: str, *, reply_text: str | None = None) -> dict:
    message = {
        "from": {"username": "authorized_user"},
        "chat": {"id": 123},
        "text": text,
        "entities": [{"type": "bot_command"}],
    }
    if reply_text is not None:
        message["reply_to_message"] = {"text": reply_text}
    return {"update_id": update_id, "message": message}


@pytest.fixture
def recall_service():
    service = Mock()
    service.get_state_for_telegram_username = AsyncMock(return_value=("authorized_user", make_state()))
    service.enable_for_username = AsyncMock(
        return_value=RecallEnableResult(
            status=RecallEnableStatus.ENABLED,
            normalized_username="authorized_user",
            user_id=1,
            state=make_state(),
        )
    )
    service.disable_for_user = AsyncMock()
    service.remove_word_completely = AsyncMock()
    service.postpone_word = AsyncMock()
    service.bump_words = AsyncMock(return_value=make_state())
    return service


@pytest.fixture
def processor(recall_service):
    @asynccontextmanager
    async def provider():
        yield recall_service

    offset_store = Mock()
    offset_store.get_update_offset.return_value = 0
    with patch("runestone.telegram.commands.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test-token"
        return TelegramCommandProcessor(offset_store, provider)


def test_constructor_uses_configured_token(recall_service):
    provider = Mock()
    offset_store = Mock()

    with patch("runestone.telegram.commands.settings") as mock_settings:
        mock_settings.telegram_bot_token = "configured-token"
        processor = TelegramCommandProcessor(offset_store, provider)

    assert processor.base_url == "https://api.telegram.org/botconfigured-token"
    assert processor.provide_recall_transaction is provider


def test_constructor_rejects_missing_token(recall_service):
    with (
        patch("runestone.telegram.commands.settings") as mock_settings,
        pytest.raises(ValueError, match="Telegram bot token is required"),
    ):
        mock_settings.telegram_bot_token = ""
        TelegramCommandProcessor(Mock(), Mock())


@pytest.mark.anyio
async def test_send_message_success_includes_optional_parse_mode(processor):
    response = MagicMock()
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch("runestone.telegram.commands.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        sent = await processor._send_message(123, "hello", "MarkdownV2")

    assert sent is True
    client.post.assert_awaited_once_with(
        "https://api.telegram.org/bottest-token/sendMessage",
        json={"chat_id": 123, "text": "hello", "parse_mode": "MarkdownV2"},
    )


@pytest.mark.anyio
@pytest.mark.parametrize("failure_kind", ["http-status", "network"])
async def test_send_message_returns_false_for_http_failures(processor, failure_kind):
    request = httpx.Request("POST", "https://api.telegram.org/sendMessage")
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error",
        request=request,
        response=httpx.Response(500, request=request),
    )
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    if failure_kind == "network":
        client.post.side_effect = httpx.ConnectError("offline", request=request)

    with patch("runestone.telegram.commands.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        assert await processor._send_message(123, "hello") is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"ok": False, "description": "rejected"},
        "not-an-object",
        {"ok": True, "result": "not-a-list"},
        {"ok": True, "result": []},
    ],
)
async def test_fetch_updates_rejects_api_errors_malformed_and_empty_results(processor, payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    with patch("runestone.telegram.commands.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        assert await processor._fetch_updates() == []

    client.get.assert_awaited_once_with(
        "https://api.telegram.org/bottest-token/getUpdates",
        params={"offset": 0, "timeout": 30},
    )


@pytest.mark.anyio
async def test_fetch_updates_returns_empty_when_offset_read_fails(processor):
    processor.offset_store.get_update_offset.side_effect = OSError("unreadable")

    with patch("runestone.telegram.commands.httpx.AsyncClient") as client_class:
        assert await processor._fetch_updates() == []

    client_class.assert_not_called()


def test_outcome_types_are_immutable():
    message = TelegramMessage(chat_id=123, text="hello")
    outcome = CommandOutcome(status="handled", messages=(message,))

    with pytest.raises(AttributeError):
        message.text = "changed"
    with pytest.raises(AttributeError):
        outcome.status = "ignored"


@pytest.mark.anyio
async def test_fetches_and_sorts_before_opening_per_update_transactions(processor, recall_service):
    events: list[str] = []

    @asynccontextmanager
    async def provider():
        events.append("open")
        yield recall_service
        events.append("close")

    processor.provide_recall_transaction = provider
    processor._fetch_updates = AsyncMock(
        side_effect=lambda: events.append("fetch")
        or [
            command_update(2, "/stop"),
            command_update(1, "/state"),
        ]
    )
    processor._send_message = AsyncMock(side_effect=lambda *_args: events.append("send") or True)

    await processor.process_updates()

    assert events == ["fetch", "open", "close", "send", "open", "close", "send"]
    assert processor.offset_store.set_update_offset.call_args == call(3)
    assert recall_service.get_state_for_telegram_username.await_args_list == [
        call("authorized_user"),
        call("authorized_user"),
    ]


@pytest.mark.anyio
async def test_structural_ignores_do_not_open_provider_and_advance(processor):
    provider = Mock(side_effect=AssertionError("provider must not open"))
    processor.provide_recall_transaction = provider
    processor._fetch_updates = AsyncMock(
        return_value=[
            {"update_id": 4, "edited_message": {}},
            {"update_id": 5, "message": {"chat": {"id": 123}, "from": {}}},
            command_update(6, "/help"),
            {
                "update_id": 7,
                "message": {
                    "chat": {"id": 123},
                    "from": {"username": "authorized_user"},
                    "text": "/state",
                    "entities": [],
                },
            },
        ]
    )

    await processor.process_updates()

    provider.assert_not_called()
    processor.offset_store.set_update_offset.assert_called_once_with(8)


@pytest.mark.anyio
async def test_commit_failure_discards_messages_stops_batch_and_retains_failing_offset(
    processor,
    recall_service,
):
    provider_count = 0

    @asynccontextmanager
    async def provider():
        nonlocal provider_count
        provider_count += 1
        yield recall_service
        if provider_count == 2:
            raise SQLAlchemyError("commit failed")

    processor.provide_recall_transaction = provider
    processor._fetch_updates = AsyncMock(
        return_value=[
            command_update(10, "/state"),
            command_update(11, "/state"),
            command_update(12, "/state"),
        ]
    )
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    assert provider_count == 2
    assert processor._send_message.await_count == 1
    processor.offset_store.set_update_offset.assert_called_once_with(11)


@pytest.mark.anyio
async def test_post_commit_session_close_failure_sends_and_advances(
    processor,
    recall_service,
    caplog,
):
    events: list[str] = []

    class Transaction:
        async def __aenter__(self):
            events.append("transaction_open")

        async def __aexit__(self, exc_type, _exc, _traceback):
            assert exc_type is None
            events.append("commit")

    class Session:
        def begin(self):
            return Transaction()

    @asynccontextmanager
    async def session_provider():
        yield Session()
        events.append("close")
        raise SQLAlchemyError("session close failed")

    processor.provide_recall_transaction = provide_recall_transaction
    processor._fetch_updates = AsyncMock(return_value=[command_update(10, "/state")])
    processor._send_message = AsyncMock(return_value=True)

    with (
        patch("runestone.recall.providers.provide_db_session", session_provider),
        patch("runestone.recall.providers._create_recall_service", return_value=recall_service),
    ):
        await processor.process_updates()

    assert events == ["transaction_open", "commit", "close"]
    processor._send_message.assert_awaited_once()
    processor.offset_store.set_update_offset.assert_called_once_with(11)
    assert "Failed to close recall command session after commit" in caplog.text


@pytest.mark.anyio
async def test_wrapped_database_failure_is_retryable_and_retains_offset(processor, recall_service):
    database_error = SQLAlchemyError("statement failed")
    wrapped = RecallOperationError("failed")
    wrapped.__cause__ = database_error
    recall_service.enable_for_username.side_effect = wrapped
    processor._fetch_updates = AsyncMock(return_value=[command_update(7, "/start")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    processor._send_message.assert_not_awaited()
    processor.offset_store.set_update_offset.assert_not_called()


@pytest.mark.anyio
async def test_unknown_non_database_failure_rolls_back_sends_generic_and_advances(
    processor,
    recall_service,
):
    lifecycle: list[str] = []

    @asynccontextmanager
    async def provider():
        lifecycle.append("open")
        try:
            yield recall_service
        except Exception:
            lifecycle.append("rollback")
            raise
        else:
            lifecycle.append("commit")
        finally:
            lifecycle.append("close")

    processor.provide_recall_transaction = provider
    recall_service.enable_for_username.side_effect = TypeError("broken collaborator")
    processor._fetch_updates = AsyncMock(return_value=[command_update(7, "/start")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    assert lifecycle == ["open", "rollback", "close"]
    processor._send_message.assert_awaited_once_with(
        123,
        "Sorry, an error occurred while processing your command.",
        None,
    )
    processor.offset_store.set_update_offset.assert_called_once_with(8)


@pytest.mark.anyio
async def test_expected_domain_error_rolls_back_preserves_response_and_advances(
    processor,
    recall_service,
):
    lifecycle: list[str] = []

    @asynccontextmanager
    async def provider():
        try:
            yield recall_service
        except Exception:
            lifecycle.append("rollback")
            raise

    processor.provide_recall_transaction = provider
    recall_service.remove_word_completely.side_effect = WordNotFoundError("kontanter", "authorized_user")
    processor._fetch_updates = AsyncMock(
        return_value=[command_update(9, "/remove", reply_text="🇸🇪 kontanter\n🇬🇧 cash")]
    )
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    assert lifecycle == ["rollback"]
    processor._send_message.assert_awaited_once_with(
        123,
        "Word 'kontanter' not found in your vocabulary.",
        None,
    )
    processor.offset_store.set_update_offset.assert_called_once_with(10)


@pytest.mark.anyio
async def test_post_commit_send_failure_logs_and_advances(processor, caplog):
    processor._fetch_updates = AsyncMock(return_value=[command_update(3, "/state")])
    processor._send_message = AsyncMock(return_value=False)

    await processor.process_updates()

    assert "Failed to send Telegram command response" in caplog.text
    processor.offset_store.set_update_offset.assert_called_once_with(4)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (RecallEnableStatus.USER_NOT_FOUND, "I couldn't find a Runestone account"),
        (RecallEnableStatus.USER_INACTIVE, "Your Runestone account is not active"),
        (RecallEnableStatus.INVALID_USERNAME, "not authorized"),
    ],
)
async def test_start_preserves_profile_link_responses(processor, recall_service, status, expected):
    recall_service.enable_for_username.return_value = RecallEnableResult(
        status=status,
        normalized_username="authorized_user",
        user_id=1 if status is RecallEnableStatus.USER_INACTIVE else None,
    )
    processor._fetch_updates = AsyncMock(return_value=[command_update(1, "/start")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    assert expected in processor._send_message.await_args.args[1]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("was_already_enabled", "expected"),
    [
        (False, "Bot started! You will receive daily vocabulary words."),
        (True, "Bot is already active. You will continue receiving daily vocabulary words."),
    ],
)
async def test_start_new_and_repeated_link_preserve_responses(
    processor,
    recall_service,
    was_already_enabled,
    expected,
):
    recall_service.enable_for_username.return_value = RecallEnableResult(
        status=RecallEnableStatus.ENABLED,
        normalized_username="authorized_user",
        user_id=1,
        state=make_state(),
        was_already_enabled=was_already_enabled,
    )
    processor._fetch_updates = AsyncMock(return_value=[command_update(1, "/start")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    recall_service.enable_for_username.assert_awaited_once_with("authorized_user", 123)
    processor._send_message.assert_awaited_once_with(123, expected, None)


@pytest.mark.anyio
async def test_start_duplicate_profile_link_preserves_conflict_response(processor, recall_service):
    recall_service.enable_for_username.side_effect = TelegramUsernameConflictError("authorized_user")
    processor._fetch_updates = AsyncMock(return_value=[command_update(2, "/start")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    assert "linked to multiple Runestone accounts" in processor._send_message.await_args.args[1]
    processor.offset_store.set_update_offset.assert_called_once_with(3)


@pytest.mark.anyio
async def test_stop_disables_authorized_user(processor, recall_service):
    state = make_state(enabled=True, chat_id=456)
    recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    processor._fetch_updates = AsyncMock(return_value=[command_update(3, "/stop")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    recall_service.disable_for_user.assert_awaited_once_with(1, chat_id=456)
    processor._send_message.assert_awaited_once_with(
        123,
        "Bot stopped. You will no longer receive vocabulary words.",
        None,
    )


@pytest.mark.anyio
async def test_unauthorized_command_preserves_response(processor, recall_service):
    recall_service.get_state_for_telegram_username.return_value = ("unknown", None)
    processor._fetch_updates = AsyncMock(return_value=[command_update(4, "/state")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    processor._send_message.assert_awaited_once_with(
        123,
        "Sorry, you are not authorized to use this bot.",
        None,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "expected_fragments"),
    [
        (make_state(enabled=False), ("Is Active: ❌ No", "No words selected for today.")),
        (
            make_state(
                enabled=True,
                words=[
                    RecallQueueWord(id=1, word_phrase="kontanter"),
                    RecallQueueWord(id=2, word_phrase="biljett"),
                ],
            ),
            ("Is Active: ✅ Yes", "- kontanter\n- biljett"),
        ),
    ],
)
async def test_state_preserves_enabled_disabled_and_word_list_rendering(
    processor,
    recall_service,
    state,
    expected_fragments,
):
    recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    processor._fetch_updates = AsyncMock(return_value=[command_update(5, "/state")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    rendered = processor._send_message.await_args.args[1]
    assert rendered.startswith("Current State")
    assert all(fragment in rendered for fragment in expected_fragments)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("command", "reply_text", "expected"),
    [
        ("/remove", None, "Please reply to a word message to remove it."),
        ("/remove", "plain text", "Could not find a word to remove in the replied message."),
        ("/postpone", None, "Please reply to a word message to postpone it."),
        ("/postpone", "plain text", "Could not find a word to postpone in the replied message."),
    ],
)
async def test_remove_and_postpone_preserve_reply_guidance(
    processor,
    recall_service,
    command,
    reply_text,
    expected,
):
    processor._fetch_updates = AsyncMock(return_value=[command_update(6, command, reply_text=reply_text)])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    processor._send_message.assert_awaited_once_with(123, expected, None)
    recall_service.remove_word_completely.assert_not_awaited()
    recall_service.postpone_word.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("command", "service_method", "expected"),
    [
        ("/remove", "remove_word_completely", "Word 'kontanter' removed from vocabulary."),
        (
            "/postpone",
            "postpone_word",
            "Word 'kontanter' postponed (removed from today's selection).",
        ),
    ],
)
async def test_remove_and_postpone_success(
    processor,
    recall_service,
    command,
    service_method,
    expected,
):
    state = make_state(words=[RecallQueueWord(id=1, word_phrase="kontanter")])
    recall_service.get_state_for_telegram_username.return_value = ("authorized_user", state)
    processor._fetch_updates = AsyncMock(
        return_value=[command_update(7, command, reply_text="🇸🇪 *kontanter*\n🇬🇧 cash")]
    )
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    getattr(recall_service, service_method).assert_awaited_once_with(state, "kontanter")
    processor._send_message.assert_awaited_once_with(123, expected, None)


@pytest.mark.anyio
async def test_postpone_not_in_selection_preserves_response(processor, recall_service):
    recall_service.postpone_word.side_effect = WordNotInSelectionError("kontanter")
    processor._fetch_updates = AsyncMock(
        return_value=[command_update(8, "/postpone", reply_text="🇸🇪 kontanter\n🇬🇧 cash")]
    )
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    processor._send_message.assert_awaited_once_with(
        123,
        "Word 'kontanter' was not in today's selection.",
        None,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("words", "expected"),
    [
        (
            [RecallQueueWord(id=1, word_phrase="kontanter"), RecallQueueWord(id=2, word_phrase="biljett")],
            "Daily selection updated! Selected 2 new words for today.",
        ),
        ([], "Daily selection cleared. No new words available at this time."),
    ],
)
async def test_bump_words_preserves_nonempty_and_empty_responses(
    processor,
    recall_service,
    words,
    expected,
):
    original = make_state()
    recall_service.get_state_for_telegram_username.return_value = ("authorized_user", original)
    recall_service.bump_words.return_value = make_state(words=words)
    processor._fetch_updates = AsyncMock(return_value=[command_update(9, "/bump_words")])
    processor._send_message = AsyncMock(return_value=True)

    await processor.process_updates()

    recall_service.bump_words.assert_awaited_once_with(original)
    processor._send_message.assert_awaited_once_with(123, expected, None)


@pytest.mark.anyio
async def test_offset_write_failure_keeps_committed_command_response(processor, caplog):
    processor._fetch_updates = AsyncMock(return_value=[command_update(10, "/state")])
    processor._send_message = AsyncMock(return_value=True)
    processor.offset_store.set_update_offset.side_effect = OSError("read-only filesystem")

    await processor.process_updates()

    processor._send_message.assert_awaited_once()
    assert "Failed to update Telegram polling offset" in caplog.text


def test_parse_word_from_reply_text_handles_markdown(processor):
    assert processor._parse_word_from_reply_text("🇸🇪 *kontanter*\n🇬🇧 cash") == "kontanter"
    assert processor._parse_word_from_reply_text("not a recall message") is None
