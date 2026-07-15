"""Database-backed recall state orchestration and selection rules."""

from collections.abc import Awaitable, Callable
from dataclasses import replace

from sqlalchemy.exc import SQLAlchemyError

from runestone.core.exceptions import (
    RecallOperationError,
    RecallStateNotFoundError,
    TelegramUsernameConflictError,
    WordNotFoundError,
    WordNotInSelectionError,
)
from runestone.db.models import User
from runestone.db.recall_repository import RecallRepository
from runestone.services.recall_types import RecallEnableResult, RecallEnableStatus, RecallQueueWord, RecallState
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService
from runestone.utils.telegram import normalize_telegram_username


class RecallService:
    """Owns reusable recall-state rules independent of Telegram transport."""

    def __init__(
        self,
        recall_repository: RecallRepository,
        vocabulary_service: VocabularyService,
        user_service: UserService,
        settings,
    ):
        self.recall_repository = recall_repository
        self.vocabulary_service = vocabulary_service
        self.user_service = user_service
        self.words_per_day = settings.words_per_day
        self.cooldown_days = settings.cooldown_days

    async def get_state_for_telegram_username(self, username: str) -> tuple[str | None, RecallState | None]:
        """Resolve a Telegram username to the current recall state, if any."""
        normalized_username = normalize_telegram_username(username)
        if normalized_username is None:
            return None, None

        try:
            users = await self.user_service.get_users_by_telegram_username(normalized_username)
            if not users:
                return normalized_username, None

            if len(users) > 1:
                raise TelegramUsernameConflictError(normalized_username)

            user = users[0]
            if not user.active:
                return normalized_username, None

            state = await self.recall_repository.get_recall_state(user.id)
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to load recall state", details=str(exc)) from exc

        result = (
            self._disabled_state_for_user(user) if state is None else self._with_username(state, user.telegram_username)
        )
        return normalized_username, result

    async def enable_for_username(self, username: str, chat_id: int) -> RecallEnableResult:
        """Enable recall and report whether it was already enabled before this request."""
        normalized_username = normalize_telegram_username(username)
        if normalized_username is None:
            return RecallEnableResult(status=RecallEnableStatus.INVALID_USERNAME)

        try:
            users = await self.user_service.get_users_by_telegram_username(normalized_username)
            if not users:
                return RecallEnableResult(
                    status=RecallEnableStatus.USER_NOT_FOUND,
                    normalized_username=normalized_username,
                )

            if len(users) > 1:
                raise TelegramUsernameConflictError(normalized_username)

            user = users[0]
            if not user.active:
                return RecallEnableResult(
                    status=RecallEnableStatus.USER_INACTIVE,
                    normalized_username=normalized_username,
                    user_id=user.id,
                )
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to enable recall", details=str(exc)) from exc

        try:
            previous_state = await self.recall_repository.get_recall_state_for_update(user.id)
            was_already_enabled = previous_state is not None and previous_state.is_enabled
            state = await self.recall_repository.upsert_for_user(user.id, chat_id=chat_id, is_enabled=True)
            await self.recall_repository.commit()
            return RecallEnableResult(
                status=RecallEnableStatus.ENABLED,
                normalized_username=normalized_username,
                user_id=user.id,
                state=state,
                was_already_enabled=was_already_enabled,
            )
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to enable recall", details=str(exc)) from exc
        except Exception:
            await self.recall_repository.rollback()
            raise

    async def disable_for_user(self, user_id: int, chat_id: int | None = None) -> RecallState:
        """Disable recall delivery without affecting account activation."""
        try:
            state = await self.recall_repository.upsert_for_user(user_id, chat_id=chat_id, is_enabled=False)
            await self.recall_repository.commit()
            return state
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to disable recall", details=str(exc)) from exc
        except Exception:
            await self.recall_repository.rollback()
            raise

    async def get_active_recall_states(self) -> list[RecallState]:
        """Load recall states eligible for scheduled delivery."""
        try:
            states = await self.recall_repository.get_active_recall_states()
            return states
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to load active recall states", details=str(exc)) from exc

    async def bump_words(self, state: RecallState) -> RecallState:
        """Replace the current queue with a fresh selection."""
        try:
            current_state = await self.recall_repository.get_recall_state_for_update(state.user_id)
            if current_state is None:
                raise RecallStateNotFoundError(state.user_id)
            refreshed = await self._bump_words_locked(current_state)
            await self.recall_repository.commit()
            return refreshed
        except RecallOperationError:
            await self.recall_repository.rollback()
            raise
        except Exception as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to replace recall queue", details=str(exc)) from exc

    async def _bump_words_locked(self, state: RecallState) -> RecallState:
        """Replace a queue while its recall-state row is locked by the caller."""
        bumped_word_ids = [word.id for word in state.daily_selection]
        portion_words = await self._select_bumped_daily_portion(
            state.user_id, excluded_word_ids=bumped_word_ids or None
        )

        if len(portion_words) < self.words_per_day:
            needed = self.words_per_day - len(portion_words)
            fallback_ids = bumped_word_ids + [word.id for word in portion_words]
            portion_words.extend(
                await self._select_bumped_daily_portion(
                    state.user_id,
                    excluded_word_ids=list(dict.fromkeys(fallback_ids)) or None,
                    limit=needed,
                )
            )

        await self.recall_repository.replace_queue(state.user_id, portion_words, next_word_index=0)
        refreshed = await self.recall_repository.get_recall_state(state.user_id)
        return refreshed or state

    async def remove_word_completely(self, state: RecallState, word_phrase: str) -> RecallState:
        """Soft-delete one vocabulary item and remove it from the recall queue."""
        try:
            # 1. Lock the aggregate before resolving or mutating its vocabulary entry.
            current_state = await self.recall_repository.get_recall_state_for_update(state.user_id)
            if current_state is None:
                raise RecallStateNotFoundError(state.user_id)
            matching_word = await self.vocabulary_service.get_vocabulary_item_by_phrase(word_phrase, state.user_id)
            if not matching_word:
                raise WordNotFoundError(word_phrase, state.telegram_username or str(state.user_id))

            # 2. Mutate vocabulary and queue in the shared transaction, then refill.
            await self.vocabulary_service.deactivate_item(matching_word.id, state.user_id)
            removal = await self.recall_repository.remove_queue_word(state.user_id, matching_word.id)
            refreshed = await self.recall_repository.get_recall_state(state.user_id) or current_state
            if removal is not None:
                refreshed = await self._maintain_daily_selection_locked(refreshed)

            # 3. Commit all aggregate changes once after every invariant is restored.
            await self.recall_repository.commit()
            return refreshed
        except (RecallOperationError, WordNotFoundError):
            await self.recall_repository.rollback()
            raise
        except Exception as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to remove word from recall state", details=str(exc)) from exc

    async def postpone_word(self, state: RecallState, word_phrase: str) -> RecallState:
        """Remove one queue item, lower its urgency, and backfill the queue."""
        try:
            # 1. Lock the aggregate and resolve the owned vocabulary item.
            current_state = await self.recall_repository.get_recall_state_for_update(state.user_id)
            if current_state is None:
                raise RecallStateNotFoundError(state.user_id)
            matching_word = await self.vocabulary_service.get_vocabulary_item_by_phrase(word_phrase, state.user_id)
            if not matching_word:
                raise WordNotInSelectionError(word_phrase)

            # 2. Require queue membership before lowering urgency, then refill.
            removal = await self.recall_repository.remove_queue_word(state.user_id, matching_word.id)
            if removal is None:
                raise WordNotInSelectionError(word_phrase)

            await self.vocabulary_service.deprioritize_item(matching_word.id, state.user_id)
            refreshed = await self.recall_repository.get_recall_state(state.user_id) or current_state
            refreshed = await self._maintain_daily_selection_locked(
                refreshed,
                additionally_excluded_word_ids=[matching_word.id],
            )

            # 3. Persist vocabulary, queue, cursor, and refill as one transaction.
            await self.recall_repository.commit()
            return refreshed
        except RecallOperationError:
            await self.recall_repository.rollback()
            raise
        except Exception as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to postpone word", details=str(exc)) from exc

    async def load_current_recall_words(self, user_id: int) -> list[str]:
        """Best-effort load of the current ordered recall queue for Teacher context."""
        try:
            words = await self.recall_repository.get_current_recall_words(user_id)
            return words
        except SQLAlchemyError as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to load current recall words", details=str(exc)) from exc

    async def rollback_failed_operation(self) -> None:
        """Recover the service session after an unexpected outer-boundary failure."""
        await self.recall_repository.rollback()

    async def deliver_next_word(
        self,
        user_id: int,
        send_word: Callable[[int, RecallQueueWord], Awaitable[bool]],
        max_attempts: int = 3,
    ) -> RecallState | None:
        """Deliver and persist one user's next recall word as one locked workflow.

        The recall row stays locked while the external send callback runs. This
        deliberately serializes concurrent delivery workers for the same user;
        the accepted-send/database-commit gap remains an unavoidable external
        side-effect boundary.
        """
        try:
            # 1. Lock and prepare the authoritative state before inspecting its queue.
            current_state = await self.recall_repository.get_recall_state_for_update(user_id)
            if current_state is None or not current_state.is_enabled or current_state.telegram_chat_id is None:
                await self.recall_repository.rollback()
                return None

            if not await self.user_service.is_user_active(user_id):
                await self.recall_repository.rollback()
                return None
            current_state = await self._ensure_daily_selection_locked(current_state)

            # 2. Remove stale entries and retry replacement queues while the lock is held.
            for selection_attempt in range(max_attempts + 1):
                if not current_state.daily_selection:
                    await self.recall_repository.commit()
                    return None

                for _ in range(max(len(current_state.daily_selection), self.words_per_day)):
                    queued_word = self._next_queue_word(current_state)
                    if queued_word is None:
                        break

                    validated_word = await self.vocabulary_service.get_learnable_item(queued_word.id, user_id)
                    if validated_word is not None:
                        word_to_send = self._merge_queue_metadata(queued_word, validated_word)
                        accepted = await send_word(current_state.telegram_chat_id, word_to_send)
                        if not accepted:
                            await self.recall_repository.rollback()
                            return None

                        # 3. Persist learning metadata and cursor only after transport acceptance.
                        await self.vocabulary_service.record_learning_event(queued_word.id, user_id)
                        await self.recall_repository.advance_cursor(user_id)
                        delivered_state = replace(
                            current_state,
                            next_word_index=(current_state.next_word_index + 1) % len(current_state.daily_selection),
                        )
                        await self.recall_repository.commit()
                        return delivered_state

                    await self.recall_repository.remove_queue_word(user_id, queued_word.id)
                    refreshed = await self.recall_repository.get_recall_state(user_id)
                    if refreshed is None:
                        await self.recall_repository.rollback()
                        return None
                    current_state = await self._maintain_daily_selection_locked(refreshed)

                if selection_attempt >= max_attempts:
                    await self.recall_repository.commit()
                    return None
                current_state = await self._bump_words_locked(current_state)
        except RecallOperationError:
            await self.recall_repository.rollback()
            raise
        except Exception as exc:
            await self.recall_repository.rollback()
            raise RecallOperationError("Failed to deliver recall word", details=str(exc)) from exc

    async def remove_queue_item(self, user_id: int, vocabulary_id: int) -> bool:
        """Remove one queued item within a transaction owned by the caller.

        The method locks the recall state, compacts the queue, adjusts its cursor,
        and flushes through the repository. It never commits or rolls back. A
        user without recall state, or an item absent from the queue, is a safe
        no-op reported as ``False``.
        """
        return await self.recall_repository.remove_queue_word(user_id, vocabulary_id) is not None

    async def refill_queue(self, user_id: int) -> RecallState | None:
        """Best-effort refill a queue within a transaction owned by the caller.

        The method locks and reloads the authoritative recall state, restores the
        configured target size when eligible vocabulary exists, and flushes
        changes through the repository. It never commits or rolls back.
        """
        current_state = await self.recall_repository.get_recall_state_for_update(user_id)
        if current_state is None:
            return None
        return await self._maintain_daily_selection_locked(current_state)

    async def _ensure_daily_selection_locked(self, state: RecallState) -> RecallState:
        if state.daily_selection:
            return state

        portion_words = await self._select_daily_portion(state.user_id)
        if not portion_words:
            return state

        await self.recall_repository.replace_queue(state.user_id, portion_words, next_word_index=0)
        return await self.recall_repository.get_recall_state(state.user_id) or state

    async def _maintain_daily_selection_locked(
        self,
        state: RecallState,
        *,
        additionally_excluded_word_ids: list[int] | None = None,
    ) -> RecallState:
        needed = self.words_per_day - len(state.daily_selection)
        if needed <= 0:
            return state

        excluded_ids = list(
            dict.fromkeys([word.id for word in state.daily_selection] + (additionally_excluded_word_ids or []))
        )
        additions = await self.vocabulary_service.select_daily_candidates(
            user_id=state.user_id,
            cooldown_days=self.cooldown_days,
            limit=needed,
            excluded_word_ids=excluded_ids or None,
        )
        if not additions:
            return state

        await self.recall_repository.append_queue_words(state.user_id, additions)
        return await self.recall_repository.get_recall_state(state.user_id) or state

    async def _select_daily_portion(self, user_id: int) -> list[RecallQueueWord]:
        return await self.vocabulary_service.select_daily_candidates(
            user_id,
            self.cooldown_days,
            limit=self.words_per_day,
        )

    async def _select_bumped_daily_portion(
        self,
        user_id: int,
        *,
        excluded_word_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[RecallQueueWord]:
        return await self.vocabulary_service.select_alternative_candidates(
            user_id,
            self.cooldown_days,
            limit=self.words_per_day if limit is None else limit,
            excluded_word_ids=excluded_word_ids,
        )

    @staticmethod
    def _next_queue_word(state: RecallState) -> RecallQueueWord | None:
        """Return the cursor-selected word from a non-authoritative state snapshot."""
        if not state.daily_selection:
            return None
        return state.daily_selection[state.next_word_index % len(state.daily_selection)]

    @staticmethod
    def _merge_queue_metadata(queued_word: RecallQueueWord, validated_word: RecallQueueWord) -> RecallQueueWord:
        """Prefer persisted queue text while filling any missing optional metadata."""
        return RecallQueueWord(
            id=queued_word.id,
            word_phrase=queued_word.word_phrase or validated_word.word_phrase,
            translation=queued_word.translation or validated_word.translation,
            example_phrase=queued_word.example_phrase or validated_word.example_phrase,
        )

    @staticmethod
    def _disabled_state_for_user(user: User) -> RecallState:
        """Build a transport-facing disabled snapshot for an active linked user."""
        return RecallState(
            user_id=user.id,
            telegram_username=user.telegram_username,
            telegram_chat_id=None,
            is_enabled=False,
            next_word_index=0,
            daily_selection=[],
        )

    @staticmethod
    def _with_username(state: RecallState, telegram_username: str | None) -> RecallState:
        """Attach the linked Telegram username to a loaded state snapshot."""
        return replace(state, telegram_username=telegram_username)
