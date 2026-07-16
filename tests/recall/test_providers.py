from contextlib import asynccontextmanager
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from runestone.recall.providers import _create_recall_service, provide_recall_session, provide_recall_transaction


class RecordingTransaction:
    def __init__(self, events):
        self.events = events

    async def __aenter__(self):
        self.events.append("transaction_enter")
        return self

    async def __aexit__(self, exc_type, _exc, _traceback):
        self.events.append(("transaction_exit", exc_type))
        self.events.append("transaction_commit" if exc_type is None else "transaction_rollback")


class RecordingSession:
    def __init__(self, events):
        self.events = events
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def begin(self):
        self.events.append("transaction_begin")
        return RecordingTransaction(self.events)


def recording_session_provider(session, events, *, close_error=None):
    @asynccontextmanager
    async def provider():
        events.append("session_enter")
        try:
            yield session
        finally:
            events.append("session_exit")
        if close_error is not None:
            raise close_error

    return provider


@pytest.mark.anyio
async def test_provide_recall_transaction_owns_one_outer_transaction():
    events = []
    session = RecordingSession(events)
    service = object()

    with (
        patch(
            "runestone.recall.providers.provide_db_session",
            recording_session_provider(session, events),
        ),
        patch("runestone.recall.providers._create_recall_service", return_value=service) as create_service,
    ):
        async with provide_recall_transaction() as provided:
            events.append("consumer")
            assert provided is service

    assert events == [
        "session_enter",
        "transaction_begin",
        "transaction_enter",
        "consumer",
        ("transaction_exit", None),
        "transaction_commit",
        "session_exit",
    ]
    create_service.assert_called_once_with(session)
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_provide_recall_transaction_rolls_back_through_outer_context_on_failure():
    events = []
    session = RecordingSession(events)

    with (
        patch(
            "runestone.recall.providers.provide_db_session",
            recording_session_provider(session, events),
        ),
        patch("runestone.recall.providers._create_recall_service", return_value=object()),
    ):
        with pytest.raises(RuntimeError, match="application failed"):
            async with provide_recall_transaction():
                raise RuntimeError("application failed")

    assert events[-3:] == [
        ("transaction_exit", RuntimeError),
        "transaction_rollback",
        "session_exit",
    ]


@pytest.mark.anyio
async def test_provide_recall_transaction_suppresses_close_failure_after_commit(caplog):
    events = []
    session = RecordingSession(events)

    with (
        patch(
            "runestone.recall.providers.provide_db_session",
            recording_session_provider(
                session,
                events,
                close_error=RuntimeError("session close failed"),
            ),
        ),
        patch("runestone.recall.providers._create_recall_service", return_value=object()),
    ):
        async with provide_recall_transaction():
            events.append("consumer")

    assert events[-3:] == [
        ("transaction_exit", None),
        "transaction_commit",
        "session_exit",
    ]
    assert "Failed to close recall command session after commit" in caplog.text


@pytest.mark.anyio
async def test_provide_recall_session_never_opens_or_completes_application_transaction():
    events = []
    session = RecordingSession(events)
    service = object()

    with (
        patch(
            "runestone.recall.providers.provide_db_session",
            recording_session_provider(session, events),
        ),
        patch("runestone.recall.providers._create_recall_service", return_value=service),
    ):
        async with provide_recall_session() as provided:
            events.append("consumer")
            assert provided is service

    assert events == ["session_enter", "consumer", "session_exit"]
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


def test_create_recall_service_assembles_required_collaborators():
    session = Mock()
    recall_repository = object()
    vocabulary_repository = object()
    user_repository = object()
    vocabulary_service = object()
    user_service = object()
    model = object()

    with (
        patch("runestone.recall.providers.RecallRepository", return_value=recall_repository) as recall_repo_type,
        patch(
            "runestone.recall.providers.VocabularyRepository",
            return_value=vocabulary_repository,
        ) as vocabulary_repo_type,
        patch("runestone.recall.providers.UserRepository", return_value=user_repository) as user_repo_type,
        patch(
            "runestone.recall.providers.VocabularyService",
            return_value=vocabulary_service,
        ) as vocabulary_service_type,
        patch("runestone.recall.providers.UserService", return_value=user_service) as user_service_type,
        patch("runestone.recall.providers._get_service_llm_model", return_value=model),
        patch("runestone.recall.providers.RecallService") as recall_service_type,
    ):
        result = _create_recall_service(session)

    recall_repo_type.assert_called_once_with(session)
    vocabulary_repo_type.assert_called_once_with(session)
    user_repo_type.assert_called_once_with(session)
    vocabulary_service_type.assert_called_once_with(
        vocabulary_repository,
        ANY,
        model,
    )
    user_service_type.assert_called_once_with(user_repository)
    recall_service_type.assert_called_once_with(
        recall_repository,
        vocabulary_service,
        user_service,
        ANY,
    )
    assert result is recall_service_type.return_value
