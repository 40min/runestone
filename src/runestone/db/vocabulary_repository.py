from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, case, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import VocabularyItemCreate, VocabularyStatsResponse
from ..constants import VOCABULARY_PRIORITY_AGENT_NEW, VOCABULARY_PRIORITY_HIGH, VOCABULARY_PRIORITY_LOW
from ..schemas.vocabulary_save import (
    PriorityWordSaveItem,
    RepositoryPriorityAction,
    RepositoryPriorityResult,
    priority_word_action_name,
)
from ..utils.search import parse_search_query_with_wildcards
from .models import Vocabulary


class VocabularyRepository:
    """Repository for vocabulary-related database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_existing_word_phrases_for_batch(self, word_phrases: List[str], user_id: int) -> set[str]:
        """Get existing word_phrases for a user from the given batch."""
        if not word_phrases:
            return set()

        stmt = select(Vocabulary.word_phrase).filter(
            Vocabulary.user_id == user_id, Vocabulary.word_phrase.in_(word_phrases)
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def prioritize_existing_word_phrases(self, word_phrases: List[str], user_id: int) -> RepositoryPriorityResult:
        """Prioritize existing vocabulary rows and report missing phrases without inserting them."""
        if not word_phrases:
            return RepositoryPriorityResult(actions=[], missing_word_phrases=[])

        requested_values = ", ".join(f"(:word_phrase_{index}, {index})" for index, _ in enumerate(word_phrases))
        params = {
            "user_id": user_id,
            "min_priority": VOCABULARY_PRIORITY_HIGH,
            **{f"word_phrase_{index}": word_phrase for index, word_phrase in enumerate(word_phrases)},
        }
        stmt = text(
            f"""
            WITH requested(word_phrase, ordinal) AS (
                VALUES {requested_values}
            ),
            requested_distinct AS (
                SELECT word_phrase, MIN(ordinal) AS first_ordinal
                FROM requested
                GROUP BY word_phrase
            ),
            existing AS (
                SELECT rd.word_phrase, rd.first_ordinal, v.id, v.in_learn, v.priority_learn
                FROM requested_distinct rd
                JOIN vocabulary v ON v.user_id = :user_id AND v.word_phrase = rd.word_phrase
            ),
            updated AS (
                UPDATE vocabulary AS v
                SET
                    in_learn = TRUE,
                    priority_learn = GREATEST(v.priority_learn - 1, :min_priority),
                    updated_at = NOW()
                FROM existing e
                WHERE v.id = e.id
                RETURNING v.id, v.priority_learn
            )
            SELECT
                r.word_phrase,
                e.id AS word_id,
                CASE
                    WHEN e.id IS NULL THEN 'missing'
                    WHEN e.in_learn IS FALSE THEN 'restored'
                    WHEN u.priority_learn < e.priority_learn THEN 'prioritized'
                    ELSE 'already_prioritized'
                END AS action,
                CASE
                    WHEN e.id IS NULL THEN FALSE
                    WHEN e.in_learn IS FALSE OR u.priority_learn < e.priority_learn THEN TRUE
                    ELSE FALSE
                END AS changed
            FROM requested r
            LEFT JOIN existing e ON e.word_phrase = r.word_phrase
            LEFT JOIN updated u ON u.id = e.id
            ORDER BY r.ordinal
            """
        )

        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()
        actions: list[RepositoryPriorityAction] = []
        missing_word_phrases: list[str] = []
        updated_word_ids: list[int] = []
        for row in rows:
            action = priority_word_action_name(row["action"], default="missing")
            word_id = row["word_id"]
            word_phrase = str(row["word_phrase"])
            if action == "missing":
                missing_word_phrases.append(word_phrase)
            elif word_id is not None:
                updated_word_ids.append(int(word_id))

            actions.append(
                RepositoryPriorityAction(
                    word_phrase=word_phrase,
                    action=action,
                    word_id=int(word_id) if word_id is not None else None,
                    changed=bool(row["changed"]),
                )
            )

        await self.db.commit()
        if updated_word_ids:
            await self.db.execute(
                select(Vocabulary).where(Vocabulary.id.in_(updated_word_ids)).execution_options(populate_existing=True)
            )
        return RepositoryPriorityResult(actions=actions, missing_word_phrases=missing_word_phrases)

    async def batch_insert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
        """Batch insert vocabulary items (assumes duplicates are already filtered)."""
        vocab_objects = [
            Vocabulary(
                user_id=user_id,
                word_phrase=item.word_phrase,
                translation=item.translation,
                example_phrase=item.example_phrase,
                extra_info=item.extra_info,
                in_learn=item.in_learn,
                priority_learn=item.priority_learn,
                last_learned=None,
            )
            for item in items
        ]
        self.db.add_all(vocab_objects)
        await self.db.commit()

    async def insert_vocabulary_item(self, item: VocabularyItemCreate, user_id: int) -> Vocabulary:
        """Insert a single vocabulary item."""
        vocab = Vocabulary(
            user_id=user_id,
            word_phrase=item.word_phrase,
            translation=item.translation,
            example_phrase=item.example_phrase,
            extra_info=item.extra_info,
            in_learn=item.in_learn,
            priority_learn=item.priority_learn,
            last_learned=None,
        )
        self.db.add(vocab)
        await self.db.commit()
        await self.db.refresh(vocab)
        return vocab

    async def insert_or_prioritize_words(self, items: List[PriorityWordSaveItem], user_id: int) -> list[dict]:
        """Atomically insert missing words and prioritize existing ones in one batch."""
        if not items:
            return []

        requested_values = ", ".join(
            (f"(:word_phrase_{index}, :translation_{index}, :example_phrase_{index}, " f":extra_info_{index}, {index})")
            for index, _ in enumerate(items)
        )
        params = {
            "user_id": user_id,
            "new_word_priority": VOCABULARY_PRIORITY_AGENT_NEW,
            "min_priority": VOCABULARY_PRIORITY_HIGH,
        }
        for index, item in enumerate(items):
            params.update(
                {
                    f"word_phrase_{index}": item.word_phrase,
                    f"translation_{index}": item.translation,
                    f"example_phrase_{index}": item.example_phrase,
                    f"extra_info_{index}": item.extra_info,
                }
            )

        stmt = text(
            f"""
            WITH requested(word_phrase, translation, example_phrase, extra_info, ordinal) AS (
                VALUES {requested_values}
            ),
            requested_distinct AS (
                SELECT DISTINCT ON (word_phrase) word_phrase, translation, example_phrase, extra_info, ordinal
                FROM requested
                ORDER BY word_phrase, ordinal
            ),
            existing AS (
                SELECT rd.word_phrase, v.id, v.in_learn, v.priority_learn
                FROM requested_distinct rd
                JOIN vocabulary v ON v.user_id = :user_id AND v.word_phrase = rd.word_phrase
            ),
            upserted AS (
                INSERT INTO vocabulary
                    (user_id, word_phrase, translation, example_phrase, extra_info, in_learn, priority_learn)
                SELECT
                    :user_id, word_phrase, translation, example_phrase, extra_info, TRUE, :new_word_priority
                FROM requested_distinct
                ON CONFLICT (user_id, word_phrase) DO UPDATE
                SET
                    in_learn = TRUE,
                    priority_learn = GREATEST(vocabulary.priority_learn - 1, :min_priority),
                    extra_info = COALESCE(NULLIF(vocabulary.extra_info, ''), EXCLUDED.extra_info),
                    updated_at = NOW()
                RETURNING id, word_phrase, priority_learn, (xmax = 0) AS inserted
            )
            SELECT
                r.word_phrase,
                u.id AS word_id,
                CASE
                    WHEN u.inserted THEN 'created'
                    WHEN e.in_learn IS FALSE THEN 'restored'
                    WHEN u.priority_learn < e.priority_learn THEN 'prioritized'
                    ELSE 'already_prioritized'
                END AS action,
                CASE
                    WHEN u.inserted THEN TRUE
                    WHEN e.in_learn IS FALSE OR u.priority_learn < e.priority_learn THEN TRUE
                    ELSE FALSE
                END AS changed
            FROM requested r
            JOIN upserted u ON u.word_phrase = r.word_phrase
            LEFT JOIN existing e ON e.word_phrase = r.word_phrase
            ORDER BY r.ordinal
            """
        )
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()
        await self.db.commit()
        # Keep identity map in sync for sessions that already loaded this row.
        word_ids = [int(row["word_id"]) for row in rows]
        if word_ids:
            await self.db.execute(
                select(Vocabulary).where(Vocabulary.id.in_(word_ids)).execution_options(populate_existing=True)
            )
        return [
            {
                "word_phrase": str(row["word_phrase"]),
                "action": str(row["action"]),
                "word_id": int(row["word_id"]),
                "changed": bool(row["changed"]),
            }
            for row in rows
        ]

    async def upsert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
        """Upsert vocabulary items: update if exists, insert if not."""
        if not items:
            return

        data = [
            {
                "user_id": user_id,
                "word_phrase": item.word_phrase,
                "translation": item.translation,
                "example_phrase": item.example_phrase,
                "extra_info": item.extra_info,
                "in_learn": item.in_learn,
                "priority_learn": item.priority_learn,
                "last_learned": None,
            }
            for item in items
        ]

        stmt = insert(Vocabulary).values(data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "word_phrase"],
            set_={
                "translation": stmt.excluded.translation,
                "example_phrase": stmt.excluded.example_phrase,
                "updated_at": func.now(),
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def add_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
        """Add vocabulary items to the database, handling uniqueness (legacy method)."""
        # Get unique word_phrases from the batch
        batch_word_phrases = [item.word_phrase for item in items]

        # Get existing word_phrases for the user from this batch
        existing_word_phrases = await self.get_existing_word_phrases_for_batch(batch_word_phrases, user_id)

        # Filter items: remove duplicates within batch and existing in DB
        seen_in_batch = set()
        filtered_items = []

        for item in items:
            if item.word_phrase not in seen_in_batch and item.word_phrase not in existing_word_phrases:
                filtered_items.append(item)
                seen_in_batch.add(item.word_phrase)

        # Batch insert the filtered items
        if filtered_items:
            await self.batch_insert_vocabulary_items(filtered_items, user_id)

    async def get_vocabulary(
        self,
        user_id: int,
        limit: int,
        search_query: str | None = None,
        precise: bool = False,
        offset: int = 0,
    ) -> List[Vocabulary]:
        r"""Retrieve vocabulary items for a user, optionally filtered by search query with wildcard support."""
        stmt = select(Vocabulary).filter(Vocabulary.user_id == user_id)

        if search_query:
            if precise:
                stmt = stmt.filter(func.lower(Vocabulary.word_phrase) == search_query.lower())
            else:
                # Parse the search query, handling wildcards and escape sequences
                search_pattern = parse_search_query_with_wildcards(search_query).lower()

                # Wrap with % for substring matching only if the user did not provide any wildcards.
                if "%" not in search_pattern and "_" not in search_pattern:
                    search_pattern = f"%{search_pattern}%"

                # Use ilike with escape character for case-insensitive matching
                stmt = stmt.filter(Vocabulary.word_phrase.ilike(search_pattern, escape="\\"))

        stmt = (
            stmt.order_by(func.coalesce(Vocabulary.updated_at, Vocabulary.created_at).desc(), Vocabulary.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_vocabulary_item(self, item_id: int, user_id: int) -> Vocabulary:
        """Get a vocabulary item by ID and user_id."""
        stmt = select(Vocabulary).filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        vocab = result.scalars().first()

        if not vocab:
            raise ValueError(f"Vocabulary item with id {item_id} not found for user {user_id}")

        return vocab

    async def update_vocabulary_item(self, vocab: Vocabulary) -> Vocabulary:
        """Update a vocabulary item using explicit UPDATE statement."""
        # Use explicit UPDATE statement to ensure we update instead of insert
        stmt = (
            update(Vocabulary)
            .where(Vocabulary.id == vocab.id)
            .values(
                word_phrase=vocab.word_phrase,
                translation=vocab.translation,
                example_phrase=vocab.example_phrase,
                extra_info=vocab.extra_info,
                in_learn=vocab.in_learn,
                priority_learn=vocab.priority_learn,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        # Refresh to get updated timestamps
        await self.db.refresh(vocab)
        return vocab

    async def select_new_daily_words(
        self, user_id: int, cooldown_days: int = 7, limit: int = 100, excluded_word_ids: Optional[List[int]] = None
    ) -> List[Vocabulary]:
        """Select eligible daily words in deterministic priority/age order."""
        cutoff_date = datetime.now() - timedelta(days=cooldown_days)

        # Build base filter conditions
        base_filter = [
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(True),
            or_(Vocabulary.last_learned.is_(None), Vocabulary.last_learned < cutoff_date),
        ]

        if excluded_word_ids:
            base_filter.append(~Vocabulary.id.in_(excluded_word_ids))

        stmt = (
            select(Vocabulary)
            .filter(*base_filter)
            .order_by(Vocabulary.priority_learn.asc(), Vocabulary.updated_at.asc(), Vocabulary.id.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_vocabulary_item_for_recall(self, item_id: int, user_id: int) -> Vocabulary:
        """Get a vocabulary item by ID and user_id, ensuring it's in learning."""
        stmt = select(Vocabulary).filter(
            Vocabulary.id == item_id, Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True)
        )
        result = await self.db.execute(stmt)
        vocab = result.scalars().first()

        if not vocab:
            raise ValueError(f"Vocabulary item with id {item_id} not found for user {user_id} or not in learning")

        return vocab

    async def get_vocabulary_items_by_ids(self, item_ids: List[int], user_id: int) -> List[Vocabulary]:
        """Get vocabulary items by IDs and user_id, ensuring they're in learning."""
        if not item_ids:
            return []
        stmt = select(Vocabulary).filter(
            Vocabulary.id.in_(item_ids), Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_last_learned(self, vocab: Vocabulary) -> None:
        """Update the last_learned timestamp and increment learned_times for a vocabulary item."""
        stmt = (
            update(Vocabulary)
            .where(Vocabulary.id == vocab.id)
            .values(
                last_learned=datetime.now(timezone.utc),
                learned_times=func.coalesce(Vocabulary.learned_times, 0) + 1,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_vocabulary_item_by_word_phrase(self, word_phrase: str, user_id: int) -> Optional[Vocabulary]:
        """Get a vocabulary item by word_phrase and user_id."""
        stmt = select(Vocabulary).filter(Vocabulary.word_phrase == word_phrase, Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete_vocabulary_item_by_word_phrase(self, word_phrase: str, user_id: int) -> bool:
        """Mark a vocabulary item as not in learning (soft delete) by word phrase."""
        stmt = (
            update(Vocabulary)
            .filter(Vocabulary.word_phrase == word_phrase, Vocabulary.user_id == user_id)
            .values({"in_learn": False})
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def delete_vocabulary_item(self, item_id: int, user_id: int) -> bool:
        """Mark a vocabulary item as not in learning (soft delete)."""
        stmt = (
            update(Vocabulary)
            .filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id)
            .values({"in_learn": False})
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def hard_delete_vocabulary_item(self, item_id: int, user_id: int) -> bool:
        """Completely delete a vocabulary item from the database."""
        stmt = delete(Vocabulary).filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def get_words_in_learn_count(self, user_id: int) -> int:
        """Get count of active vocabulary items that have been studied at least once."""
        stmt = select(func.count(Vocabulary.id)).filter(
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(True),
            Vocabulary.last_learned.isnot(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_words_skipped_count(self, user_id: int) -> int:
        """Get count of vocabulary items with in_learn=False for a user."""
        stmt = select(func.count(Vocabulary.id)).filter(
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_overall_words_count(self, user_id: int) -> int:
        """Get total count of all vocabulary items for a user."""
        stmt = select(func.count(Vocabulary.id)).filter(Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_words_prioritized_count(self, user_id: int) -> int:
        """Get count of active vocabulary items with elevated priority."""
        stmt = select(func.count(Vocabulary.id)).filter(
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(True),
            Vocabulary.priority_learn < VOCABULARY_PRIORITY_LOW,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_vocabulary_stats(self, user_id: int) -> VocabularyStatsResponse:
        """Get all Vocabulary-tab counters in one aggregate query."""
        stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Vocabulary.in_learn.is_(True),
                                Vocabulary.last_learned.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("words_in_learn_count"),
            func.coalesce(
                func.sum(case((Vocabulary.in_learn.is_(False), 1), else_=0)),
                0,
            ).label("words_skipped_count"),
            func.count(Vocabulary.id).label("overall_words_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Vocabulary.in_learn.is_(True),
                                Vocabulary.priority_learn < VOCABULARY_PRIORITY_LOW,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("words_prioritized_count"),
        ).filter(Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        stats = result.mappings().one()
        return VocabularyStatsResponse(**stats)
