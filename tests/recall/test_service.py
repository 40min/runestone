from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from sqlalchemy.exc import SQLAlchemyError

from runestone.core.exceptions import (
    RecallOperationError,
    RecallQueueWordNotFoundError,
    RecallStateNotFoundError,
    TelegramUsernameConflictError,
)
from runestone.db.models import User, Vocabulary
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.recall.service import RecallService
from runestone.recall.types import RecallEnableStatus, RecallQueueWord, RecallState
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService


def make_state(
    *,
    user_id: int = 1,
    telegram_username: str | None = None,
    next_word_index: int = 0,
    daily_selection: list[RecallQueueWord] | None = None,
    is_enabled: bool = True,
) -> RecallState:
    return RecallState(
        user_id=user_id,
        telegram_username=telegram_username,
        telegram_chat_id=123,
        is_enabled=is_enabled,
        next_word_index=next_word_index,
        daily_selection=daily_selection or [],
    )


def make_word(word_id: int, word_phrase: str) -> RecallQueueWord:
    return RecallQueueWord(id=word_id, word_phrase=word_phrase)


@pytest.fixture
def recall_service():
    recall_repository = Mock()
    recall_repository.get_recall_state = AsyncMock()
    recall_repository.get_recall_state_for_update = AsyncMock()
    recall_repository.get_active_recall_states = AsyncMock(return_value=[])
    recall_repository.get_current_recall_words = AsyncMock(return_value=[])
    recall_repository.remove_queue_word = AsyncMock()
    recall_repository.replace_queue = AsyncMock()
    recall_repository.append_queue_words = AsyncMock()
    recall_repository.advance_cursor = AsyncMock()
    recall_repository.upsert_for_user = AsyncMock()
    recall_repository.commit = AsyncMock()
    recall_repository.rollback = AsyncMock()

    vocabulary_service = Mock()
    vocabulary_service.get_vocabulary_item_by_phrase = AsyncMock()
    vocabulary_service.get_learnable_item = AsyncMock()
    vocabulary_service.deactivate_item = AsyncMock()
    vocabulary_service.deprioritize_item = AsyncMock()
    vocabulary_service.deprioritize_items = AsyncMock()
    vocabulary_service.record_learning_event = AsyncMock()
    vocabulary_service.select_daily_candidates = AsyncMock(return_value=[])
    vocabulary_service.select_alternative_candidates = AsyncMock(return_value=[])

    user_service = Mock()
    user_service.get_users_by_telegram_username = AsyncMock(return_value=[])
    user_service.is_user_active = AsyncMock(return_value=True)
    settings = SimpleNamespace(words_per_day=3, cooldown_days=7)
    service = RecallService(recall_repository, vocabulary_service, user_service, settings)
    return service


@pytest.mark.anyio
async def test_get_state_for_telegram_username_returns_disabled_snapshot_for_active_user_without_state(recall_service):
    user = SimpleNamespace(id=7, telegram_username="linked_user", active=True)
    recall_service.user_service.get_users_by_telegram_username.return_value = [user]
    recall_service.recall_repository.get_recall_state.return_value = None

    normalized_username, state = await recall_service.get_state_for_telegram_username("@linked_user")

    assert normalized_username == "linked_user"
    assert state == RecallState(
        user_id=7,
        telegram_username="linked_user",
        telegram_chat_id=None,
        is_enabled=False,
        next_word_index=0,
        daily_selection=[],
    )
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_state_for_telegram_username_rejects_duplicate_links(recall_service):
    recall_service.user_service.get_users_by_telegram_username.return_value = [
        SimpleNamespace(id=1, telegram_username="dup", active=True),
        SimpleNamespace(id=2, telegram_username="dup", active=True),
    ]

    with pytest.raises(TelegramUsernameConflictError, match="multiple Runestone accounts"):
        await recall_service.get_state_for_telegram_username("dup")

    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_state_for_telegram_username_wraps_database_failure_without_owning_transaction(recall_service):
    database_error = SQLAlchemyError("database unavailable")
    recall_service.user_service.get_users_by_telegram_username.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to load recall state") as exc_info:
        await recall_service.get_state_for_telegram_username("linked")

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_state_for_telegram_username_does_not_hide_programming_errors(recall_service):
    programming_error = TypeError("broken collaborator contract")
    recall_service.user_service.get_users_by_telegram_username.side_effect = programming_error

    with pytest.raises(TypeError, match="broken collaborator contract"):
        await recall_service.get_state_for_telegram_username("linked")

    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_state_for_user_loads_transport_neutral_state(recall_service):
    state = make_state(user_id=7, telegram_username="linked")
    recall_service.recall_repository.get_recall_state.return_value = state

    result = await recall_service.get_state_for_user(7)

    assert result == state
    recall_service.recall_repository.get_recall_state.assert_awaited_once_with(7)
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_state_for_user_wraps_database_failure(recall_service):
    database_error = SQLAlchemyError("database unavailable")
    recall_service.recall_repository.get_recall_state.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to load recall state") as exc_info:
        await recall_service.get_state_for_user(7)

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_active_recall_states_delegates_filtered_batch_load_to_repository(recall_service):
    active_state = make_state(user_id=1, telegram_username="active_user")
    recall_service.recall_repository.get_active_recall_states.return_value = [active_state]

    states = await recall_service.get_active_recall_states()

    assert states == [active_state]
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_get_active_recall_states_wraps_database_failure_without_owning_transaction(recall_service):
    database_error = SQLAlchemyError("database unavailable")
    recall_service.recall_repository.get_active_recall_states.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to load active recall states") as exc_info:
        await recall_service.get_active_recall_states()

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_load_current_recall_words_keeps_successful_shared_transaction_neutral(recall_service):
    recall_service.recall_repository.get_current_recall_words.return_value = ["hej", "tack"]

    words = await recall_service.load_current_recall_words(7)

    assert words == ["hej", "tack"]
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_load_current_recall_words_recovers_best_effort_request_after_database_failure(recall_service):
    database_error = SQLAlchemyError("database unavailable")
    recall_service.recall_repository.get_current_recall_words.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to load current recall words") as exc_info:
        await recall_service.load_current_recall_words(7)

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_awaited_once_with()


@pytest.mark.anyio
async def test_enable_for_username_refuses_inactive_account(recall_service):
    inactive_user = SimpleNamespace(id=7, telegram_username="inactive", active=False)
    recall_service.user_service.get_users_by_telegram_username.return_value = [inactive_user]

    result = await recall_service.enable_for_username("@inactive", 123)

    assert result.status is RecallEnableStatus.USER_INACTIVE
    assert result.normalized_username == "inactive"
    assert result.user_id == inactive_user.id
    assert result.state is None
    recall_service.recall_repository.upsert_for_user.assert_not_awaited()
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_enable_for_username_duplicate_link_does_not_rollback(recall_service):
    recall_service.user_service.get_users_by_telegram_username.return_value = [
        SimpleNamespace(id=1, telegram_username="dup", active=True),
        SimpleNamespace(id=2, telegram_username="dup", active=True),
    ]

    with pytest.raises(TelegramUsernameConflictError, match="multiple Runestone accounts"):
        await recall_service.enable_for_username("dup", 123)

    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_enable_for_username_wraps_database_mutation_failure_without_owning_transaction(recall_service):
    user = SimpleNamespace(id=7, telegram_username="linked", active=True)
    database_error = SQLAlchemyError("write failed")
    recall_service.user_service.get_users_by_telegram_username.return_value = [user]
    recall_service.recall_repository.get_recall_state_for_update.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to enable recall") as exc_info:
        await recall_service.enable_for_username("linked", 123)

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_enable_for_username_propagates_programming_failure_without_owning_transaction(recall_service):
    user = SimpleNamespace(id=7, telegram_username="linked", active=True)
    programming_error = TypeError("broken mutation contract")
    recall_service.user_service.get_users_by_telegram_username.return_value = [user]
    recall_service.recall_repository.upsert_for_user.side_effect = programming_error

    with pytest.raises(TypeError, match="broken mutation contract"):
        await recall_service.enable_for_username("linked", 123)

    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_disable_for_user_propagates_programming_failure_without_owning_transaction(recall_service):
    programming_error = TypeError("broken mutation contract")
    recall_service.recall_repository.upsert_for_user.side_effect = programming_error

    with pytest.raises(TypeError, match="broken mutation contract"):
        await recall_service.disable_for_user(7)

    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_disable_for_user_wraps_database_failure_without_owning_transaction(recall_service):
    database_error = SQLAlchemyError("write failed")
    recall_service.recall_repository.upsert_for_user.side_effect = database_error

    with pytest.raises(RecallOperationError, match="Failed to disable recall") as exc_info:
        await recall_service.disable_for_user(7)

    assert exc_info.value.__cause__ is database_error
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_enable_for_username_reports_prior_enabled_state_and_refreshes_chat_link(recall_service):
    user = SimpleNamespace(id=7, telegram_username="linked", active=True)
    previous_state = make_state(user_id=7, is_enabled=True)
    refreshed_state = replace(previous_state, telegram_chat_id=456)
    recall_service.user_service.get_users_by_telegram_username.return_value = [user]
    recall_service.recall_repository.get_recall_state_for_update.return_value = previous_state
    recall_service.recall_repository.upsert_for_user.return_value = refreshed_state

    result = await recall_service.enable_for_username("@linked", 456)

    assert result.status is RecallEnableStatus.ENABLED
    assert result.was_already_enabled is True
    assert result.state == refreshed_state
    recall_service.recall_repository.upsert_for_user.assert_awaited_once_with(
        7,
        chat_id=456,
        is_enabled=True,
    )
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_bump_words_raises_specific_error_when_state_is_missing(recall_service):
    recall_service.recall_repository.get_recall_state_for_update.return_value = None

    with pytest.raises(RecallStateNotFoundError, match="Recall state not found"):
        await recall_service.bump_words(7)

    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_bump_words_keeps_original_queue_excluded_across_fallback_selection(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej"), make_word(8, "tack")])
    replacement = make_word(9, "ny")
    refreshed_state = make_state(user_id=1, daily_selection=[replacement, make_word(10, "sen")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.get_recall_state.return_value = refreshed_state
    recall_service.vocabulary_service.select_alternative_candidates.side_effect = [
        [replacement],
        [make_word(10, "sen")],
    ]

    result = await recall_service.bump_words(1)

    assert result == refreshed_state
    recall_service.vocabulary_service.deprioritize_items.assert_awaited_once_with([7, 8], 1)
    assert recall_service.vocabulary_service.select_alternative_candidates.await_args_list == [
        call(
            1,
            7,
            limit=3,
            excluded_word_ids=[7, 8],
        ),
        call(
            1,
            7,
            limit=2,
            excluded_word_ids=[7, 8, 9],
        ),
    ]
    recall_service.recall_repository.replace_queue.assert_awaited_once_with(
        1,
        [replacement, make_word(10, "sen")],
        next_word_index=0,
    )
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_bump_words_deprioritizes_locked_queue_before_selecting_replacements(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    replacements = [make_word(8, "tack"), make_word(9, "ny"), make_word(10, "sen")]
    refreshed_state = make_state(user_id=1, daily_selection=replacements)
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.get_recall_state.return_value = refreshed_state

    async def select_after_deprioritization(*args, **kwargs):
        recall_service.vocabulary_service.deprioritize_items.assert_awaited_once_with([7], 1)
        return replacements

    recall_service.vocabulary_service.select_alternative_candidates.side_effect = select_after_deprioritization

    result = await recall_service.bump_words(1)

    assert result == refreshed_state
    recall_service.recall_repository.replace_queue.assert_awaited_once_with(
        1,
        replacements,
        next_word_index=0,
    )


@pytest.mark.anyio
async def test_postpone_word_raises_specific_error_when_state_is_missing(recall_service):
    recall_service.recall_repository.get_recall_state_for_update.return_value = None

    with pytest.raises(RecallStateNotFoundError, match="Recall state not found"):
        await recall_service.postpone_word(make_state(user_id=7), "hej")

    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_postpone_word_excludes_removed_item_from_immediate_refill(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    shortened_state = make_state(user_id=1)
    persistence_events = []

    async def load_state(_user_id):
        persistence_events.append("load")
        return shortened_state

    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.get_recall_state.side_effect = load_state
    recall_service.recall_repository.remove_queue_word.return_value = SimpleNamespace(removed_position=0)
    recall_service.vocabulary_service.get_vocabulary_item_by_phrase.return_value = SimpleNamespace(id=7)

    result = await recall_service.postpone_word(queued_state, "hej")

    assert result == shortened_state
    recall_service.vocabulary_service.select_daily_candidates.assert_awaited_once_with(
        user_id=1,
        cooldown_days=7,
        limit=3,
        excluded_word_ids=[7],
    )
    recall_service.recall_repository.append_queue_words.assert_not_awaited()
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()
    assert persistence_events == ["load"]


@pytest.mark.anyio
async def test_postpone_queue_word_uses_locked_membership_and_refills(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    shortened_state = make_state(user_id=1)
    replacement = make_word(8, "tack")
    refreshed_state = make_state(user_id=1, daily_selection=[replacement])
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.remove_queue_word.return_value = SimpleNamespace(removed_position=0)
    recall_service.recall_repository.get_recall_state.side_effect = [shortened_state, refreshed_state]
    recall_service.vocabulary_service.select_daily_candidates.return_value = [replacement]

    result = await recall_service.postpone_queue_word(1, 7)

    assert result == refreshed_state
    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.vocabulary_service.deprioritize_item.assert_awaited_once_with(7, 1)
    recall_service.vocabulary_service.select_daily_candidates.assert_awaited_once_with(
        user_id=1,
        cooldown_days=7,
        limit=3,
        excluded_word_ids=[7],
    )
    recall_service.recall_repository.append_queue_words.assert_awaited_once_with(1, [replacement])
    recall_service.recall_repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_postpone_queue_word_rejects_id_outside_locked_selection(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state

    with pytest.raises(RecallQueueWordNotFoundError, match="not found in current selection"):
        await recall_service.postpone_queue_word(1, 99)

    recall_service.recall_repository.remove_queue_word.assert_not_awaited()
    recall_service.vocabulary_service.deprioritize_item.assert_not_awaited()


@pytest.mark.anyio
async def test_postpone_queue_word_rejects_missing_recall_state(recall_service):
    recall_service.recall_repository.get_recall_state_for_update.return_value = None

    with pytest.raises(RecallStateNotFoundError):
        await recall_service.postpone_queue_word(1, 7)

    recall_service.recall_repository.remove_queue_word.assert_not_awaited()
    recall_service.vocabulary_service.deprioritize_item.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_word_completely_returns_transaction_snapshot_without_owning_transaction(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    shortened_state = make_state(user_id=1)
    persistence_events = []

    async def load_state(_user_id):
        persistence_events.append("load")
        return shortened_state

    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.get_recall_state.side_effect = load_state
    recall_service.recall_repository.remove_queue_word.return_value = SimpleNamespace(removed_position=0)
    recall_service.vocabulary_service.get_vocabulary_item_by_phrase.return_value = SimpleNamespace(id=7)

    result = await recall_service.remove_word_completely(queued_state, "hej")

    assert result == shortened_state
    recall_service.vocabulary_service.deactivate_item.assert_awaited_once_with(7, 1)
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()
    assert persistence_events == ["load"]


@pytest.mark.anyio
async def test_remove_queue_word_from_learning_deactivates_locked_membership_and_refills(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    shortened_state = make_state(user_id=1)
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state
    recall_service.recall_repository.remove_queue_word.return_value = SimpleNamespace(removed_position=0)
    recall_service.recall_repository.get_recall_state.return_value = shortened_state

    result = await recall_service.remove_queue_word_from_learning(1, 7)

    assert result == shortened_state
    recall_service.vocabulary_service.deactivate_item.assert_awaited_once_with(7, 1)
    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.vocabulary_service.select_daily_candidates.assert_awaited_once_with(
        user_id=1,
        cooldown_days=7,
        limit=3,
        excluded_word_ids=None,
    )
    recall_service.recall_repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_queue_word_from_learning_rejects_id_outside_locked_selection(recall_service):
    queued_state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = queued_state

    with pytest.raises(RecallQueueWordNotFoundError, match="not found in current selection"):
        await recall_service.remove_queue_word_from_learning(1, 99)

    recall_service.vocabulary_service.deactivate_item.assert_not_awaited()
    recall_service.recall_repository.remove_queue_word.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_queue_word_from_learning_rejects_missing_recall_state(recall_service):
    recall_service.recall_repository.get_recall_state_for_update.return_value = None

    with pytest.raises(RecallStateNotFoundError):
        await recall_service.remove_queue_word_from_learning(1, 7)

    recall_service.vocabulary_service.deactivate_item.assert_not_awaited()
    recall_service.recall_repository.remove_queue_word.assert_not_awaited()


@pytest.mark.anyio
async def test_deliver_next_word_commits_metadata_and_wrapped_cursor_together(recall_service):
    state = make_state(user_id=1, next_word_index=2, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = state
    recall_service.recall_repository.get_recall_state.side_effect = AssertionError("read happened after commit")
    recall_service.vocabulary_service.get_learnable_item.return_value = make_word(7, "hej")
    send_word = AsyncMock(return_value=True)

    result = await recall_service.deliver_next_word(1, send_word)

    assert result == replace(state, next_word_index=0)
    send_word.assert_awaited_once_with(123, make_word(7, "hej"))
    recall_service.recall_repository.get_recall_state_for_update.assert_awaited_once_with(1)
    recall_service.vocabulary_service.record_learning_event.assert_awaited_once_with(7, 1)
    recall_service.recall_repository.advance_cursor.assert_awaited_once_with(1)
    recall_service.recall_repository.commit.assert_awaited_once()
    recall_service.recall_repository.get_recall_state.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_deliver_next_word_rolls_back_when_send_is_rejected(recall_service):
    state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = state
    recall_service.vocabulary_service.get_learnable_item.return_value = make_word(7, "hej")
    send_word = AsyncMock(return_value=False)

    result = await recall_service.deliver_next_word(1, send_word)

    assert result is None
    recall_service.vocabulary_service.record_learning_event.assert_not_awaited()
    recall_service.recall_repository.advance_cursor.assert_not_awaited()
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_deliver_next_word_wraps_unexpected_failures_as_recall_errors(recall_service):
    state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = state
    recall_service.vocabulary_service.get_learnable_item.side_effect = RuntimeError("database failed")

    with pytest.raises(RecallOperationError, match="Failed to deliver recall word") as error:
        await recall_service.deliver_next_word(1, AsyncMock())

    assert error.value.details == "database failed"
    recall_service.recall_repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_deliver_next_word_rolls_back_unusable_state(recall_service):
    recall_service.recall_repository.get_recall_state_for_update.return_value = make_state(is_enabled=False)

    result = await recall_service.deliver_next_word(1, AsyncMock())

    assert result is None
    recall_service.recall_repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_deliver_next_word_revalidates_active_user_after_state_lock(recall_service):
    state = make_state(user_id=1, daily_selection=[make_word(7, "hej")])
    recall_service.recall_repository.get_recall_state_for_update.return_value = state
    recall_service.user_service.is_user_active.return_value = False
    send_word = AsyncMock(return_value=True)

    result = await recall_service.deliver_next_word(1, send_word)

    assert result is None
    recall_service.user_service.is_user_active.assert_awaited_once_with(1)
    send_word.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_deliver_next_word_removes_invalid_queue_entry_and_commits_cleanup(recall_service):
    initial_state = make_state(user_id=1, daily_selection=[make_word(7, "stale")])
    empty_state = make_state(user_id=1)
    recall_service.recall_repository.get_recall_state_for_update.return_value = initial_state
    recall_service.recall_repository.get_recall_state.return_value = empty_state
    recall_service.vocabulary_service.get_learnable_item.return_value = None

    result = await recall_service.deliver_next_word(1, AsyncMock(), max_attempts=0)

    assert result is None
    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.recall_repository.commit.assert_awaited_once()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_deliver_next_word_refills_after_invalid_entry_before_sending(recall_service):
    stale_state = make_state(user_id=1, daily_selection=[make_word(7, "stale")])
    empty_state = make_state(user_id=1)
    replacement = make_word(9, "replacement")
    refilled_state = make_state(user_id=1, daily_selection=[replacement])
    recall_service.recall_repository.get_recall_state_for_update.return_value = stale_state
    recall_service.recall_repository.get_recall_state.side_effect = [
        empty_state,
        refilled_state,
    ]
    recall_service.vocabulary_service.get_learnable_item.side_effect = [
        None,
        replacement,
    ]
    recall_service.vocabulary_service.select_daily_candidates.return_value = [replacement]
    send_word = AsyncMock(return_value=True)

    result = await recall_service.deliver_next_word(1, send_word)

    assert result == refilled_state
    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.recall_repository.append_queue_words.assert_awaited_once_with(1, [replacement])
    send_word.assert_awaited_once_with(123, replacement)
    recall_service.vocabulary_service.record_learning_event.assert_awaited_once_with(9, 1)
    recall_service.recall_repository.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_remove_queue_item_reports_removal_without_owning_transaction(recall_service):
    recall_service.recall_repository.remove_queue_word.return_value = SimpleNamespace(
        removed_position=0,
        next_word_index=0,
    )

    assert await recall_service.remove_queue_item(1, 7) is True

    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_remove_queue_item_is_noop_without_recall_state(recall_service):
    recall_service.recall_repository.remove_queue_word.return_value = None

    assert await recall_service.remove_queue_item(1, 7) is False

    recall_service.recall_repository.remove_queue_word.assert_awaited_once_with(1, 7)
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_refill_queue_fills_to_target_without_owning_transaction(recall_service):
    shortened_state = make_state(user_id=1, daily_selection=[make_word(8, "keep")])
    replacement = make_word(9, "replacement")
    refilled_state = make_state(
        user_id=1,
        daily_selection=[make_word(8, "keep"), replacement],
    )
    recall_service.recall_repository.get_recall_state_for_update.return_value = shortened_state
    recall_service.recall_repository.get_recall_state.return_value = refilled_state
    recall_service.vocabulary_service.select_daily_candidates.return_value = [replacement]

    assert await recall_service.refill_queue(1) == refilled_state

    recall_service.vocabulary_service.select_daily_candidates.assert_awaited_once_with(
        user_id=1,
        cooldown_days=7,
        limit=2,
        excluded_word_ids=[8],
    )
    recall_service.recall_repository.append_queue_words.assert_awaited_once_with(1, [replacement])
    recall_service.recall_repository.commit.assert_not_awaited()
    recall_service.recall_repository.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_postpone_single_eligible_word_does_not_reselect_it(db_session):
    user = User(
        name="Recall",
        surname="Postpone",
        email="recall-postpone@example.com",
        hashed_password="hashed",
        timezone="UTC",
    )
    db_session.add(user)
    await db_session.flush()
    word = Vocabulary(user_id=user.id, word_phrase="hej", translation="hello")
    db_session.add(word)
    await db_session.flush()

    settings = SimpleNamespace(words_per_day=1, cooldown_days=7)
    repository = RecallRepository(db_session)
    service = RecallService(
        repository,
        VocabularyService(VocabularyRepository(db_session), settings, AsyncMock()),
        UserService(UserRepository(db_session)),
        settings,
    )
    await repository.upsert_for_user(user.id, chat_id=123, is_enabled=True)
    await repository.replace_queue(user.id, [make_word(word.id, "hej")])
    await repository.commit()
    state = await repository.get_recall_state(user.id)
    assert state is not None

    result = await service.postpone_word(state, "hej")

    assert result.daily_selection == []
    assert result.next_word_index == 0
    persisted = await repository.get_recall_state(user.id)
    assert persisted is not None
    assert persisted.daily_selection == []
    assert persisted.next_word_index == 0


@pytest.mark.anyio
async def test_delivery_rechecks_active_user_after_concurrent_deactivation(db_session_factory):
    delivery_session = db_session_factory()
    deactivation_session = db_session_factory()
    try:
        user = User(
            name="Recall",
            surname="Race",
            email="recall-active-race@example.com",
            hashed_password="hashed",
            timezone="UTC",
            active=True,
        )
        delivery_session.add(user)
        await delivery_session.flush()
        word = Vocabulary(user_id=user.id, word_phrase="hej", translation="hello")
        delivery_session.add(word)
        await delivery_session.flush()
        user_id = user.id
        vocabulary_id = word.id

        settings = SimpleNamespace(words_per_day=1, cooldown_days=7)
        repository = RecallRepository(delivery_session)
        service = RecallService(
            repository,
            VocabularyService(VocabularyRepository(delivery_session), settings, AsyncMock()),
            UserService(UserRepository(delivery_session)),
            settings,
        )
        await repository.upsert_for_user(user_id, chat_id=123, is_enabled=True)
        await repository.replace_queue(user_id, [make_word(vocabulary_id, "hej")])
        await repository.commit()

        active_states = await service.get_active_recall_states()
        assert [state.user_id for state in active_states] == [user_id]
        assert user.active is True  # Keep a stale active entity cached in the delivery session.

        concurrently_updated_user = await deactivation_session.get(User, user_id)
        assert concurrently_updated_user is not None
        concurrently_updated_user.active = False
        await deactivation_session.commit()

        send_word = AsyncMock(return_value=True)
        result = await service.deliver_next_word(user_id, send_word)

        assert result is None
        send_word.assert_not_awaited()
        persisted = await repository.get_recall_state(user_id)
        assert persisted is not None
        assert persisted.next_word_index == 0
    finally:
        await delivery_session.rollback()
        await deactivation_session.rollback()
        await delivery_session.close()
        await deactivation_session.close()


@pytest.mark.anyio
async def test_delivery_rolls_back_learning_metadata_when_cursor_update_fails(db_session):
    user = User(
        name="Recall",
        surname="Delivery",
        email="recall-delivery@example.com",
        hashed_password="hashed",
        timezone="UTC",
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    word = Vocabulary(user_id=user.id, word_phrase="hej", translation="hello")
    db_session.add(word)
    await db_session.flush()
    user_id = user.id
    vocabulary_id = word.id
    await db_session.commit()

    settings = SimpleNamespace(words_per_day=1, cooldown_days=7)
    recall_repository = RecallRepository(db_session)
    vocabulary_service = VocabularyService(VocabularyRepository(db_session), settings, AsyncMock())
    service = RecallService(
        recall_repository,
        vocabulary_service,
        UserService(UserRepository(db_session)),
        settings,
    )
    await recall_repository.upsert_for_user(user_id, chat_id=123, is_enabled=True)
    await recall_repository.replace_queue(user_id, [make_word(vocabulary_id, "hej")])
    await recall_repository.commit()
    recall_repository.advance_cursor = AsyncMock(side_effect=RuntimeError("cursor failed"))

    with pytest.raises(RecallOperationError, match="Failed to deliver recall word"):
        await service.deliver_next_word(user_id, AsyncMock(return_value=True))

    await db_session.refresh(word)
    state = await recall_repository.get_recall_state(user_id)
    assert word.learned_times == 0
    assert word.last_learned is None
    assert state is not None
    assert state.next_word_index == 0
