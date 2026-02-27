from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import VocabularyItemCreate
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
        self, user_id: int, limit: int, search_query: str | None = None, precise: bool = False
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

        stmt = stmt.order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc()).limit(limit)
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
        """Select new daily words for a user, prioritizing words marked for priority learning."""
        cutoff_date = datetime.now() - timedelta(days=cooldown_days)

        # Build base filter conditions
        base_filter = [
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(True),
            or_(Vocabulary.last_learned.is_(None), Vocabulary.last_learned < cutoff_date),
        ]

        if excluded_word_ids:
            base_filter.append(~Vocabulary.id.in_(excluded_word_ids))

        # First: select priority words
        stmt_prioritized = (
            select(Vocabulary)
            .filter(*base_filter, Vocabulary.priority_learn.is_(True))
            .order_by(func.random())
            .limit(limit)
        )
        result_prioritized = await self.db.execute(stmt_prioritized)
        prioritized = list(result_prioritized.scalars().all())

        # If we have enough priority words, return them
        if len(prioritized) >= limit:
            return prioritized

        # Fill remaining slots with non-priority words
        remaining = limit - len(prioritized)
        prioritized_ids = [w.id for w in prioritized]

        # Build filter for regular words (excluding already selected priority words)
        regular_filter = base_filter + [Vocabulary.priority_learn.is_(False)]
        if prioritized_ids:
            regular_filter.append(~Vocabulary.id.in_(prioritized_ids))

        stmt_regular = select(Vocabulary).filter(*regular_filter).order_by(func.random()).limit(remaining)
        result_regular = await self.db.execute(stmt_regular)
        regular = list(result_regular.scalars().all())

        return prioritized + regular

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
        """Get count of vocabulary items with in_learn=True AND last_learned IS NOT NULL for a user."""
        stmt = select(func.count(Vocabulary.id)).filter(
            Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True), Vocabulary.last_learned.isnot(None)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_words_skipped_count(self, user_id: int) -> int:
        """Get count of vocabulary items with in_learn=False for a user."""
        stmt = select(func.count(Vocabulary.id)).filter(Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_overall_words_count(self, user_id: int) -> int:
        """Get total count of all vocabulary items for a user."""
        stmt = select(func.count(Vocabulary.id)).filter(Vocabulary.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
