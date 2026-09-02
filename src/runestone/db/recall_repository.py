"""Persistence helpers for recall user state and queue items."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from sqlalchemy import Integer, and_, cast, column, delete, extract, func, or_, select, table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from runestone.db.models import RecallQueueItemDB, RecallUserStateDB, User, Vocabulary
from runestone.recall.types import RecallQueueWord, RecallState


@dataclass(frozen=True, slots=True)
class QueueRemovalResult:
    """Authoritative queue and cursor outcome after removing one item."""

    removed_position: int
    next_word_index: int


class RecallRepository:
    """Owns database persistence for recall state and ordered queue items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_recall_state(self, user_id: int) -> RecallState | None:
        """Load one user's recall state and ordered queue."""
        row = await self._load_state_row(user_id)
        if row is None:
            return None
        queue = await self._load_queue(user_id)
        return self._to_state(row, queue)

    async def get_recall_state_for_update(self, user_id: int) -> RecallState | None:
        """Lock and load one user's recall state and ordered queue."""
        row = await self._load_state_row_for_update(user_id)
        if row is None:
            return None
        queue = await self._load_queue(user_id)
        return self._to_state(row, queue)

    async def get_delivery_state_for_update(self, user_id: int) -> RecallState | None:
        """Lock delivery settings without loading queue or vocabulary data."""
        row = await self._load_state_row_for_update(user_id)
        return None if row is None else self._to_state(row, [])

    async def load_locked_recall_queue(self, state: RecallState) -> RecallState:
        """Load queue data after the caller has accepted locked delivery settings."""
        return replace(state, daily_selection=await self._load_queue(state.user_id))

    async def get_delivery_candidate_user_ids(self, now: datetime | None = None) -> list[int]:
        """Return enabled active users currently inside their local delivery window."""
        timezone_names = table("pg_timezone_names", column("name"), schema="pg_catalog")
        local_hour = cast(
            extract(
                "hour",
                func.timezone(timezone_names.c.name, now or datetime.now(timezone.utc)),
            ),
            Integer,
        )
        stmt = (
            select(RecallUserStateDB.user_id)
            .join(User, User.id == RecallUserStateDB.user_id)
            .join(timezone_names, timezone_names.c.name == User.timezone)
            .where(
                RecallUserStateDB.is_enabled.is_(True),
                User.active.is_(True),
                or_(
                    and_(
                        RecallUserStateDB.recall_start_hour < RecallUserStateDB.recall_end_hour,
                        local_hour >= RecallUserStateDB.recall_start_hour,
                        local_hour < RecallUserStateDB.recall_end_hour,
                    ),
                    and_(
                        RecallUserStateDB.recall_start_hour > RecallUserStateDB.recall_end_hour,
                        or_(
                            local_hour >= RecallUserStateDB.recall_start_hour,
                            local_hour < RecallUserStateDB.recall_end_hour,
                        ),
                    ),
                ),
            )
            .order_by(RecallUserStateDB.user_id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_locked_delivery_settings(
        self,
        state: RecallState,
        recall_start_hour: int,
        recall_end_hour: int,
        is_enabled: bool,
    ) -> RecallState:
        """Persist settings after the caller has locked the recall aggregate."""
        stmt = (
            update(RecallUserStateDB)
            .where(RecallUserStateDB.user_id == state.user_id)
            .values(
                recall_start_hour=recall_start_hour,
                recall_end_hour=recall_end_hour,
                is_enabled=is_enabled,
                updated_at=func.now(),
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount != 1:
            raise ValueError(f"Recall state for user {state.user_id} not found")
        await self.db.flush()
        return RecallState(
            user_id=state.user_id,
            telegram_username=state.telegram_username,
            telegram_chat_id=state.telegram_chat_id,
            is_enabled=is_enabled,
            recall_start_hour=recall_start_hour,
            recall_end_hour=recall_end_hour,
            next_word_index=state.next_word_index,
            daily_selection=state.daily_selection,
        )

    async def upsert_for_user(self, user_id: int, *, chat_id: int | None, is_enabled: bool) -> RecallState:
        """Atomically create or update recall-delivery linkage for one user."""
        stmt = (
            insert(RecallUserStateDB)
            .values(
                user_id=user_id,
                telegram_chat_id=chat_id,
                is_enabled=is_enabled,
                next_word_index=0,
            )
            .on_conflict_do_update(
                index_elements=[RecallUserStateDB.user_id],
                set_={
                    "telegram_chat_id": chat_id,
                    "is_enabled": is_enabled,
                    "updated_at": func.now(),
                },
            )
            .returning(RecallUserStateDB)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        row = result.scalars().one()
        queue = await self._load_queue(user_id)
        return self._to_state(row, queue)

    async def replace_queue(
        self, user_id: int, queue_words: Iterable[RecallQueueWord], next_word_index: int = 0
    ) -> None:
        """Replace the full ordered recall queue for one user."""
        row = await self._require_state_row_for_update(user_id)
        await self.db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == user_id))
        for position, word in enumerate(queue_words):
            self.db.add(
                RecallQueueItemDB(
                    user_id=user_id,
                    vocabulary_id=word.id,
                    position=position,
                )
            )
        row.next_word_index = next_word_index
        await self.db.flush()

    async def append_queue_words(self, user_id: int, queue_words: Iterable[RecallQueueWord]) -> None:
        """Append new words to the end of the ordered queue."""
        await self._require_state_row_for_update(user_id)
        existing_queue = await self._load_queue(user_id)
        start_position = len(existing_queue)
        for offset, word in enumerate(queue_words):
            self.db.add(
                RecallQueueItemDB(
                    user_id=user_id,
                    vocabulary_id=word.id,
                    position=start_position + offset,
                )
            )
        await self.db.flush()

    async def remove_queue_word(self, user_id: int, vocabulary_id: int) -> QueueRemovalResult | None:
        """Remove an item, compact its queue, and adjust its cursor atomically.

        A missing recall state or queue item is a safe no-op. The returned cursor
        is derived from the state row locked by this operation, not a caller's
        potentially stale snapshot.
        """
        state_row = await self._load_state_row_for_update(user_id)
        if state_row is None:
            return None

        queue_rows = await self._load_queue_rows(user_id)
        removed_position = next(
            (item.position for item in queue_rows if item.vocabulary_id == vocabulary_id),
            None,
        )
        if removed_position is None:
            return None

        remaining_vocabulary_ids = [item.vocabulary_id for item in queue_rows if item.vocabulary_id != vocabulary_id]

        # Delete and rebuild while holding the state lock. Direct in-place
        # renumbering can transiently violate the PostgreSQL position unique key.
        await self.db.execute(delete(RecallQueueItemDB).where(RecallQueueItemDB.user_id == user_id))
        for position, remaining_vocabulary_id in enumerate(remaining_vocabulary_ids):
            self.db.add(
                RecallQueueItemDB(
                    user_id=user_id,
                    vocabulary_id=remaining_vocabulary_id,
                    position=position,
                )
            )

        state_row.next_word_index = self._cursor_after_removal(
            current_index=state_row.next_word_index,
            removed_position=removed_position,
            new_length=len(remaining_vocabulary_ids),
        )

        await self.db.flush()
        return QueueRemovalResult(
            removed_position=removed_position,
            next_word_index=state_row.next_word_index,
        )

    async def advance_cursor(self, user_id: int) -> None:
        """Advance and wrap the cursor against the authoritative queue length."""
        row = await self._require_state_row_for_update(user_id)
        queue_length = await self._queue_length(user_id)
        row.next_word_index = (row.next_word_index + 1) % queue_length if queue_length else 0
        await self.db.flush()

    async def get_current_recall_words(self, user_id: int) -> list[str]:
        """Load the current ordered recall words for Teacher context."""
        queue = await self._load_queue(user_id)
        return [item.word_phrase.strip() for item in queue if item.word_phrase.strip()]

    async def commit(self) -> None:
        """Commit pending persistence changes."""
        await self.db.commit()

    async def rollback(self) -> None:
        """Rollback pending persistence changes."""
        await self.db.rollback()

    async def _load_state_row(self, user_id: int) -> RecallUserStateDB | None:
        stmt = select(RecallUserStateDB).where(RecallUserStateDB.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _load_state_row_for_update(self, user_id: int) -> RecallUserStateDB | None:
        stmt = select(RecallUserStateDB).where(RecallUserStateDB.user_id == user_id).with_for_update()
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _require_state_row_for_update(self, user_id: int) -> RecallUserStateDB:
        row = await self._load_state_row_for_update(user_id)
        if row is None:
            raise ValueError(f"Recall state for user {user_id} not found")
        return row

    async def _load_queue_rows(self, user_id: int) -> list[RecallQueueItemDB]:
        stmt = (
            select(RecallQueueItemDB)
            .where(RecallQueueItemDB.user_id == user_id)
            .order_by(RecallQueueItemDB.position.asc(), RecallQueueItemDB.vocabulary_id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _load_queue(self, user_id: int) -> list[RecallQueueWord]:
        queues = await self._load_queues([user_id])
        return queues.get(user_id, [])

    async def _load_queues(self, user_ids: Iterable[int]) -> dict[int, list[RecallQueueWord]]:
        """Load ordered queues for multiple users in one query."""
        selected_user_ids = list(user_ids)
        if not selected_user_ids:
            return {}

        queue_alias = aliased(RecallQueueItemDB)
        stmt = (
            select(
                queue_alias.user_id,
                queue_alias.vocabulary_id,
                Vocabulary.word_phrase,
                Vocabulary.translation,
                Vocabulary.example_phrase,
            )
            .join(Vocabulary, Vocabulary.id == queue_alias.vocabulary_id)
            .where(queue_alias.user_id.in_(selected_user_ids))
            .order_by(queue_alias.user_id.asc(), queue_alias.position.asc(), queue_alias.vocabulary_id.asc())
        )
        result = await self.db.execute(stmt)
        queues: dict[int, list[RecallQueueWord]] = {user_id: [] for user_id in selected_user_ids}
        for user_id, vocabulary_id, word_phrase, translation, example_phrase in result.all():
            queues[user_id].append(
                RecallQueueWord(
                    id=vocabulary_id,
                    word_phrase=word_phrase,
                    translation=translation,
                    example_phrase=example_phrase,
                )
            )
        return queues

    async def _queue_length(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(RecallQueueItemDB).where(RecallQueueItemDB.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _cursor_after_removal(current_index: int, removed_position: int, new_length: int) -> int:
        """Keep the cursor on the same logical next item after compaction."""
        if new_length <= 0:
            return 0
        next_index = current_index - 1 if removed_position < current_index else current_index
        return 0 if next_index >= new_length else max(next_index, 0)

    @staticmethod
    def _to_state(
        row: RecallUserStateDB,
        queue: list[RecallQueueWord],
        *,
        telegram_username: str | None = None,
    ) -> RecallState:
        return RecallState(
            user_id=row.user_id,
            telegram_username=telegram_username,
            telegram_chat_id=row.telegram_chat_id,
            is_enabled=row.is_enabled,
            recall_start_hour=row.recall_start_hour,
            recall_end_hour=row.recall_end_hour,
            next_word_index=row.next_word_index,
            daily_selection=queue,
        )
