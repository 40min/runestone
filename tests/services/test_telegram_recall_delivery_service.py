"""Focused tests for Telegram recall sending flow."""

from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import httpx
import pytest

from runestone.services.recall_types import RecallQueueWord, RecallState
from runestone.services.telegram_recall_delivery_service import TelegramRecallDeliveryService


@pytest.fixture
def mock_settings():
    settings = Mock()
    settings.telegram_bot_token = "token"
    settings.words_per_day = 3
    settings.cooldown_days = 7
    settings.recall_start_hour = 0
    settings.recall_end_hour = 24
    return settings


@pytest.fixture
def mock_recall_service():
    service = Mock()
    service.get_active_recall_states = AsyncMock(return_value=[])
    service.deliver_next_word = AsyncMock()
    return service


def test_init_requires_bot_token(mock_recall_service, mock_settings):
    mock_settings.telegram_bot_token = ""

    with pytest.raises(ValueError, match="Telegram bot token is required"):
        TelegramRecallDeliveryService(mock_recall_service, mock_settings)


@pytest.mark.anyio
async def test_send_next_recall_word_skips_when_outside_hours(mock_recall_service, mock_settings):
    mock_settings.recall_start_hour = 12
    mock_settings.recall_end_hour = 13
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)

    with patch("runestone.services.telegram_recall_delivery_service.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 8
        await service.send_next_recall_word()

    mock_recall_service.get_active_recall_states.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("hour", "inside_window"),
    [(8, False), (9, True), (16, True), (17, False), (23, False)],
)
async def test_send_next_recall_word_uses_inclusive_start_exclusive_end(
    mock_recall_service,
    mock_settings,
    hour,
    inside_window,
):
    mock_settings.recall_start_hour = 9
    mock_settings.recall_end_hour = 17
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)

    with patch("runestone.services.telegram_recall_delivery_service.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = hour
        await service.send_next_recall_word()

    if inside_window:
        mock_recall_service.get_active_recall_states.assert_awaited_once_with()
    else:
        mock_recall_service.get_active_recall_states.assert_not_awaited()


@pytest.mark.anyio
async def test_send_next_recall_word_processes_enabled_users(mock_recall_service, mock_settings):
    state = RecallState(
        user_id=1,
        telegram_username="tester",
        telegram_chat_id=123,
        is_enabled=True,
        next_word_index=0,
        daily_selection=[RecallQueueWord(id=7, word_phrase="hej", translation="hi", example_phrase="Hej!")],
    )
    mock_recall_service.get_active_recall_states.return_value = [state]
    word = RecallQueueWord(id=7, word_phrase="hej", translation="hi", example_phrase="Hej!")

    async def deliver(_user_id, send_word, *, max_attempts):
        assert max_attempts == 3
        assert await send_word(123, word) is True
        return state

    mock_recall_service.deliver_next_word.side_effect = deliver
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)

    with (
        patch("runestone.services.telegram_recall_delivery_service.datetime") as mock_datetime,
        patch.object(service, "_send_word_message", new=AsyncMock(return_value=True)) as mock_send,
    ):
        mock_datetime.now.return_value.hour = 10
        await service.send_next_recall_word()

    mock_send.assert_awaited_once_with(
        123,
        {"id": 7, "word_phrase": "hej", "translation": "hi", "example_phrase": "Hej!"},
    )
    assert mock_recall_service.deliver_next_word.await_args.args[0] == 1


@pytest.mark.anyio
async def test_process_user_recall_word_delegates_workflow(mock_recall_service, mock_settings):
    state = RecallState(
        user_id=1,
        telegram_username="tester",
        telegram_chat_id=123,
        is_enabled=True,
        next_word_index=0,
        daily_selection=[RecallQueueWord(id=7, word_phrase="hej", translation="hi", example_phrase="Hej!")],
    )
    mock_recall_service.deliver_next_word.return_value = state
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)

    await service._process_user_recall_word(state, max_attempts=2)

    mock_recall_service.deliver_next_word.assert_awaited_once_with(
        1,
        service._send_queue_word,
        max_attempts=2,
    )


@pytest.mark.anyio
async def test_send_queue_word_converts_dto_to_message_payload(mock_recall_service, mock_settings):
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)
    service._send_word_message = AsyncMock(return_value=True)
    word = RecallQueueWord(id=7, word_phrase="hej", translation="hi", example_phrase="Hej!")

    assert await service._send_queue_word(123, word) is True

    service._send_word_message.assert_awaited_once_with(
        123,
        {"id": 7, "word_phrase": "hej", "translation": "hi", "example_phrase": "Hej!"},
    )


@pytest.mark.anyio
async def test_unexpected_delivery_error_propagates(mock_recall_service, mock_settings):
    state = RecallState(
        user_id=1,
        telegram_username="tester",
        telegram_chat_id=123,
        is_enabled=True,
        next_word_index=0,
        daily_selection=[RecallQueueWord(id=7, word_phrase="hej")],
    )
    mock_recall_service.deliver_next_word.side_effect = RuntimeError("database failed")
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)

    with pytest.raises(RuntimeError, match="database failed"):
        await service._process_user_recall_word(state)


@pytest.mark.anyio
async def test_send_next_recall_word_isolates_one_user_failure(mock_recall_service, mock_settings):
    states = [
        RecallState(user_id=1, telegram_username="first", telegram_chat_id=101, is_enabled=True),
        RecallState(user_id=2, telegram_username="second", telegram_chat_id=202, is_enabled=True),
        RecallState(user_id=3, telegram_username="third", telegram_chat_id=303, is_enabled=True),
    ]
    mock_recall_service.get_active_recall_states.return_value = states
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)
    service._process_user_recall_word = AsyncMock(side_effect=[RuntimeError("first failed"), None, None])

    with patch("runestone.services.telegram_recall_delivery_service.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 10
        await service.send_next_recall_word()

    assert service._process_user_recall_word.await_args_list == [call(state) for state in states]


@pytest.mark.anyio
async def test_send_word_message_escapes_markdown_and_uses_valid_markdown_v2(mock_recall_service, mock_settings):
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch("runestone.services.telegram_recall_delivery_service.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        accepted = await service._send_word_message(
            123,
            {
                "word_phrase": "hej_[x]!",
                "translation": "hi (there)",
                "example_phrase": "Hej - du!",
            },
        )

    assert accepted is True
    client.post.assert_awaited_once_with(
        "https://api.telegram.org/bottoken/sendMessage",
        json={
            "chat_id": 123,
            "text": "🇸🇪 *hej\\_\\[x\\]\\!*\n🇬🇧 hi \\(there\\)\n\n💡 _Example:_ Hej \\- du\\!",
            "parse_mode": "MarkdownV2",
        },
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "outcome",
    ["api-rejected", "malformed", "http-error", "timeout", "transport-error"],
)
async def test_send_word_message_rejects_every_unsuccessful_transport_outcome(
    mock_recall_service,
    mock_settings,
    outcome,
):
    service = TelegramRecallDeliveryService(mock_recall_service, mock_settings)
    request = httpx.Request("POST", "https://api.telegram.org/sendMessage")
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": False}
    if outcome == "malformed":
        response.json.side_effect = ValueError("invalid json")
    elif outcome == "http-error":
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error",
            request=request,
            response=httpx.Response(500, request=request),
        )

    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    if outcome == "timeout":
        client.post.side_effect = httpx.ReadTimeout("timed out", request=request)
    elif outcome == "transport-error":
        client.post.side_effect = httpx.ConnectError("offline", request=request)

    with patch("runestone.services.telegram_recall_delivery_service.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        assert await service._send_word_message(123, {"word_phrase": "hej", "translation": "hi"}) is False
