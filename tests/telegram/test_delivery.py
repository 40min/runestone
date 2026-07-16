"""Tests for scheduled Telegram recall delivery session scoping."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from runestone.recall.types import RecallQueueWord, RecallState
from runestone.telegram.delivery import TelegramRecallDelivery


class RecordingRecallProvider:
    """Yield a predetermined service per call while recording scope lifetime."""

    def __init__(self, *services):
        self.services = services
        self.call_count = 0
        self.events: list[tuple[str, int]] = []

    def __call__(self):
        index = self.call_count
        self.call_count += 1
        service = self.services[index]

        @asynccontextmanager
        async def context():
            self.events.append(("open", index))
            try:
                yield service
            finally:
                self.events.append(("close", index))

        return context()


@pytest.fixture
def mock_settings():
    settings = Mock()
    settings.telegram_bot_token = "token"
    settings.recall_start_hour = 0
    settings.recall_end_hour = 24
    return settings


def make_service(*, active_states=None):
    service = Mock()
    service.get_active_recall_states = AsyncMock(return_value=active_states or [])
    service.deliver_next_word = AsyncMock()
    return service


def make_state(user_id: int, username: str) -> RecallState:
    return RecallState(
        user_id=user_id,
        telegram_username=username,
        telegram_chat_id=100 + user_id,
        is_enabled=True,
    )


def test_init_requires_bot_token(mock_settings):
    mock_settings.telegram_bot_token = ""

    with pytest.raises(ValueError, match="Telegram bot token is required"):
        TelegramRecallDelivery(Mock(), mock_settings)


@pytest.mark.anyio
async def test_outside_delivery_hours_opens_no_recall_session(mock_settings):
    mock_settings.recall_start_hour = 12
    mock_settings.recall_end_hour = 13
    provider = Mock(side_effect=AssertionError("provider should not be called"))
    delivery = TelegramRecallDelivery(provider, mock_settings)

    with patch("runestone.telegram.delivery.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 8
        await delivery.send_next_recall_word()

    provider.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("hour", "inside_window"),
    [(8, False), (9, True), (16, True), (17, False), (23, False)],
)
async def test_delivery_window_has_inclusive_start_and_exclusive_end(
    mock_settings,
    hour,
    inside_window,
):
    mock_settings.recall_start_hour = 9
    mock_settings.recall_end_hour = 17
    provider = RecordingRecallProvider(make_service())
    delivery = TelegramRecallDelivery(provider, mock_settings)

    with patch("runestone.telegram.delivery.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = hour
        await delivery.send_next_recall_word()

    assert provider.call_count == int(inside_window)


@pytest.mark.anyio
async def test_enumeration_closes_before_fresh_session_for_each_user(mock_settings):
    states = [make_state(1, "first"), make_state(2, "second")]
    enumeration_service = make_service(active_states=states)
    first_user_service = make_service()
    second_user_service = make_service()
    provider = RecordingRecallProvider(
        enumeration_service,
        first_user_service,
        second_user_service,
    )
    delivery = TelegramRecallDelivery(provider, mock_settings)

    with patch("runestone.telegram.delivery.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 10
        await delivery.send_next_recall_word()

    enumeration_service.get_active_recall_states.assert_awaited_once_with()
    first_user_service.deliver_next_word.assert_awaited_once_with(
        1,
        delivery._send_queue_word,
        max_attempts=3,
    )
    second_user_service.deliver_next_word.assert_awaited_once_with(
        2,
        delivery._send_queue_word,
        max_attempts=3,
    )
    assert provider.events == [
        ("open", 0),
        ("close", 0),
        ("open", 1),
        ("close", 1),
        ("open", 2),
        ("close", 2),
    ]


@pytest.mark.anyio
async def test_failed_user_session_closes_and_later_user_still_runs(mock_settings):
    states = [make_state(1, "first"), make_state(2, "second")]
    enumeration_service = make_service(active_states=states)
    failed_service = make_service()
    failed_service.deliver_next_word.side_effect = RuntimeError("database failed")
    later_service = make_service()
    provider = RecordingRecallProvider(enumeration_service, failed_service, later_service)
    delivery = TelegramRecallDelivery(provider, mock_settings)

    with patch("runestone.telegram.delivery.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 10
        await delivery.send_next_recall_word()

    later_service.deliver_next_word.assert_awaited_once()
    assert provider.events[-4:] == [
        ("open", 1),
        ("close", 1),
        ("open", 2),
        ("close", 2),
    ]


@pytest.mark.anyio
async def test_process_user_delegates_locked_workflow(mock_settings):
    state = make_state(1, "tester")
    recall_service = make_service()
    recall_service.deliver_next_word.return_value = state
    delivery = TelegramRecallDelivery(Mock(), mock_settings)

    await delivery._process_user_recall_word(recall_service, state, max_attempts=2)

    recall_service.deliver_next_word.assert_awaited_once_with(
        1,
        delivery._send_queue_word,
        max_attempts=2,
    )


@pytest.mark.anyio
async def test_send_queue_word_converts_dto_to_payload(mock_settings):
    delivery = TelegramRecallDelivery(Mock(), mock_settings)
    delivery._send_word_message = AsyncMock(return_value=True)
    word = RecallQueueWord(id=7, word_phrase="hej", translation="hi", example_phrase="Hej!")

    assert await delivery._send_queue_word(123, word) is True
    delivery._send_word_message.assert_awaited_once_with(
        123,
        {"id": 7, "word_phrase": "hej", "translation": "hi", "example_phrase": "Hej!"},
    )


@pytest.mark.anyio
async def test_send_word_message_escapes_markdown_v2(mock_settings):
    delivery = TelegramRecallDelivery(Mock(), mock_settings)
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch("runestone.telegram.delivery.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        accepted = await delivery._send_word_message(
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
async def test_send_word_message_rejects_unsuccessful_transport_outcome(
    mock_settings,
    outcome,
):
    delivery = TelegramRecallDelivery(Mock(), mock_settings)
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

    with patch("runestone.telegram.delivery.httpx.AsyncClient") as client_class:
        client_class.return_value.__aenter__.return_value = client
        assert await delivery._send_word_message(123, {"word_phrase": "hej", "translation": "hi"}) is False
