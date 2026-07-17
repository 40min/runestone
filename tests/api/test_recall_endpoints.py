from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.core.exceptions import RecallOperationError, RecallQueueWordNotFoundError, RecallStateNotFoundError
from runestone.recall.types import RecallQueueWord, RecallState


def make_state(
    *,
    user_id: int = 1,
    is_enabled: bool = True,
    words: list[RecallQueueWord] | None = None,
) -> RecallState:
    return RecallState(
        user_id=user_id,
        telegram_username="linked",
        telegram_chat_id=123,
        is_enabled=is_enabled,
        next_word_index=2,
        daily_selection=words or [],
    )


@pytest.fixture
async def recall_api_client(client_with_overrides):
    service = Mock()
    service.get_state_for_user = AsyncMock()
    service.bump_words = AsyncMock()
    service.postpone_queue_word = AsyncMock()
    service.remove_queue_word_from_learning = AsyncMock()

    db = Mock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    async def override_db():
        yield db

    async for client, _ in client_with_overrides(
        recall_service=service,
        db_override=override_db,
    ):
        yield client, service, db


async def test_get_recall_returns_expected_unconfigured_state(recall_api_client):
    client, service, db = recall_api_client
    service.get_state_for_user.return_value = None

    response = await client.get("/api/recall")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "delivery_enabled": False,
        "words": [],
    }
    service.get_state_for_user.assert_awaited_once_with(client.user.id)
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


async def test_get_recall_serializes_only_display_safe_queue_fields(recall_api_client):
    client, service, db = recall_api_client
    service.get_state_for_user.return_value = make_state(
        user_id=client.user.id,
        is_enabled=False,
        words=[
            RecallQueueWord(
                id=42,
                word_phrase="kontanter",
                translation="cash",
                example_phrase="Jag betalar med kontanter.",
            )
        ],
    )

    response = await client.get("/api/recall")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "delivery_enabled": False,
        "words": [
            {
                "id": 42,
                "word_phrase": "kontanter",
                "translation": "cash",
                "example_phrase": "Jag betalar med kontanter.",
            }
        ],
    }
    assert "user_id" not in response.text
    assert "telegram" not in response.text
    assert "next_word_index" not in response.text
    db.commit.assert_not_awaited()


async def test_bump_recall_commits_once_and_returns_authoritative_queue(recall_api_client):
    client, service, db = recall_api_client
    updated = make_state(user_id=client.user.id, words=[RecallQueueWord(id=8, word_phrase="tack")])
    service.bump_words.return_value = updated

    response = await client.post("/api/recall/bump")

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [8]
    service.get_state_for_user.assert_not_awaited()
    service.bump_words.assert_awaited_once_with(client.user.id)
    db.commit.assert_awaited_once_with()
    db.rollback.assert_not_awaited()


@pytest.mark.parametrize(
    ("path", "service_method"),
    [
        ("/api/recall/words/42/postpone", "postpone_queue_word"),
        ("/api/recall/words/42/remove", "remove_queue_word_from_learning"),
    ],
)
async def test_word_mutations_use_authenticated_user_and_vocabulary_id(
    recall_api_client,
    path,
    service_method,
):
    client, service, db = recall_api_client
    updated = make_state(user_id=client.user.id, words=[RecallQueueWord(id=99, word_phrase="ny")])
    getattr(service, service_method).return_value = updated

    response = await client.post(path)

    assert response.status_code == 200
    assert [word["id"] for word in response.json()["words"]] == [99]
    getattr(service, service_method).assert_awaited_once_with(client.user.id, 42)
    db.commit.assert_awaited_once_with()
    db.rollback.assert_not_awaited()


@pytest.mark.parametrize(
    ("path", "configure_failure"),
    [
        ("/api/recall/bump", "bump"),
        ("/api/recall/words/42/postpone", "postpone"),
        ("/api/recall/words/42/remove", "remove"),
    ],
)
async def test_mutations_map_unconfigured_recall_to_conflict(
    recall_api_client,
    path,
    configure_failure,
):
    client, service, db = recall_api_client
    if configure_failure == "bump":
        service.bump_words.side_effect = RecallStateNotFoundError(client.user.id)
    elif configure_failure == "postpone":
        service.postpone_queue_word.side_effect = RecallStateNotFoundError(client.user.id)
    else:
        service.remove_queue_word_from_learning.side_effect = RecallStateNotFoundError(client.user.id)

    response = await client.post(path)

    assert response.status_code == 409
    assert "send /start" in response.json()["detail"]
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("path", "service_method"),
    [
        ("/api/recall/words/42/postpone", "postpone_queue_word"),
        ("/api/recall/words/42/remove", "remove_queue_word_from_learning"),
    ],
)
async def test_word_mutations_hide_queue_ownership_behind_not_found(
    recall_api_client,
    path,
    service_method,
):
    _client, service, db = recall_api_client
    getattr(service, service_method).side_effect = RecallQueueWordNotFoundError(42)

    response = await _client.post(path)

    assert response.status_code == 404
    assert response.json()["detail"] == "Recall word not found in current selection"
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once_with()


async def test_mutation_failure_rolls_back_and_returns_generic_detail(recall_api_client):
    client, service, db = recall_api_client
    service.postpone_queue_word.side_effect = RecallOperationError(
        "Failed to postpone word",
        details="sensitive database failure",
    )

    response = await client.post("/api/recall/words/42/postpone")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to update recall selection"
    assert "sensitive" not in response.text
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once_with()


async def test_commit_failure_rolls_back_and_returns_generic_detail(recall_api_client):
    client, service, db = recall_api_client
    service.postpone_queue_word.return_value = make_state(user_id=client.user.id)
    db.commit.side_effect = RuntimeError("commit unavailable")

    response = await client.post("/api/recall/words/42/postpone")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to update recall selection"
    service.postpone_queue_word.assert_awaited_once_with(client.user.id, 42)
    db.commit.assert_awaited_once_with()
    db.rollback.assert_awaited_once_with()


async def test_get_failure_returns_generic_detail(recall_api_client):
    client, service, _db = recall_api_client
    service.get_state_for_user.side_effect = RecallOperationError(
        "Failed to load recall state",
        details="sensitive database failure",
    )

    response = await client.get("/api/recall")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to retrieve recall selection"
    assert "sensitive" not in response.text


async def test_unexpected_get_failure_returns_generic_detail(recall_api_client):
    client, service, _db = recall_api_client
    service.get_state_for_user.side_effect = RuntimeError("sensitive programming failure")

    response = await client.get("/api/recall")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to retrieve recall selection"
    assert "sensitive" not in response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/recall"),
        ("post", "/api/recall/bump"),
        ("post", "/api/recall/words/42/postpone"),
        ("post", "/api/recall/words/42/remove"),
    ],
)
async def test_recall_routes_require_authentication(client_no_db, method, path):
    response = await getattr(client_no_db, method)(path)

    assert response.status_code == 403
