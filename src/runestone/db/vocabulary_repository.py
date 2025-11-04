"""
Repository classes for database operations.

This module contains repository classes that encapsulate database
logic for different entities.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, or_
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..api.schemas import VocabularyItemCreate
from ..utils.search import parse_search_query_with_wildcards
from .models import Vocabulary


class VocabularyRepository:
    """Repository for vocabulary-related database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_existing_word_phrases_for_batch(self, word_phrases: List[str], user_id: int) -> set[str]:
        """Get existing word_phrases for a user from the given batch."""
        if not word_phrases:
            return set()
        result = (
            self.db.query(Vocabulary.word_phrase)
            .filter(Vocabulary.user_id == user_id, Vocabulary.word_phrase.in_(word_phrases))
            .all()
        )
        return {row[0] for row in result}

    def batch_insert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
        """Batch insert vocabulary items (assumes duplicates are already filtered)."""
        vocab_objects = [
            Vocabulary(
                user_id=user_id,
                word_phrase=item.word_phrase,
                translation=item.translation,
                example_phrase=item.example_phrase,
                extra_info=item.extra_info,
                in_learn=item.in_learn,
                last_learned=None,
            )
            for item in items
        ]
        self.db.add_all(vocab_objects)
        self.db.commit()

    def insert_vocabulary_item(self, item: VocabularyItemCreate, user_id: int) -> Vocabulary:
        """Insert a single vocabulary item."""
        vocab = Vocabulary(
            user_id=user_id,
            word_phrase=item.word_phrase,
            translation=item.translation,
            example_phrase=item.example_phrase,
            extra_info=item.extra_info,
            in_learn=item.in_learn,
            last_learned=None,
        )
        self.db.add(vocab)
        self.db.commit()
        self.db.refresh(vocab)
        return vocab

    def upsert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
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
                "updated_at": datetime.now(),
            },
        )
        self.db.execute(stmt)
        self.db.commit()

    def add_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int):
        """Add vocabulary items to the database, handling uniqueness (legacy method)."""
        # Get unique word_phrases from the batch
        batch_word_phrases = [item.word_phrase for item in items]

        # Get existing word_phrases for the user from this batch
        existing_word_phrases = self.get_existing_word_phrases_for_batch(batch_word_phrases, user_id)

        # Filter items: remove duplicates within batch and existing in DB
        seen_in_batch = set()
        filtered_items = []

        for item in items:
            if item.word_phrase not in seen_in_batch and item.word_phrase not in existing_word_phrases:
                filtered_items.append(item)
                seen_in_batch.add(item.word_phrase)

        # Batch insert the filtered items
        if filtered_items:
            self.batch_insert_vocabulary_items(filtered_items, user_id)

    def get_vocabulary(
        self, user_id: int, limit: int, search_query: str | None = None, precise: bool = False
    ) -> List[Vocabulary]:
        r"""Retrieve vocabulary items for a user, optionally filtered by search query with wildcard support.

        The search performs a case-insensitive substring match by default. For example,
        searching for "apple" will match "apples" and "pineapple".

        Supports wildcards:
        - '*' matches zero or more characters
        - '?' matches exactly one character

        Special SQL characters (%, _, \) in the search query are treated as literal characters.
        """
        query = self.db.query(Vocabulary).filter(Vocabulary.user_id == user_id)

        if search_query:
            if precise:
                query = query.filter(func.lower(Vocabulary.word_phrase) == search_query.lower())
            else:
                # Parse the search query, handling wildcards and escape sequences
                search_pattern = parse_search_query_with_wildcards(search_query).lower()

                # Wrap with % for substring matching only if the user did not provide any wildcards.
                if "%" not in search_pattern and "_" not in search_pattern:
                    search_pattern = f"%{search_pattern}%"

                # Use ilike with escape character for case-insensitive matching
                query = query.filter(Vocabulary.word_phrase.ilike(search_pattern, escape="\\"))

        return query.order_by(Vocabulary.created_at.desc(), Vocabulary.id.desc()).limit(limit).all()

    def get_vocabulary_item(self, item_id: int, user_id: int) -> Vocabulary:
        """Get a vocabulary item by ID and user_id."""
        vocab = self.db.query(Vocabulary).filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id).first()

        if not vocab:
            raise ValueError(f"Vocabulary item with id {item_id} not found for user {user_id}")

        return vocab

    def update_vocabulary_item(self, vocab: Vocabulary) -> Vocabulary:
        """Commit and refresh a vocabulary item."""
        self.db.commit()
        self.db.refresh(vocab)
        return vocab

    def select_new_daily_words(
        self, user_id: int, cooldown_days: int = 7, limit: int = 100, excluded_word_ids: Optional[List[int]] = None
    ) -> List[Vocabulary]:
        """
        Select new daily words for a user randomly, excluding recently learned words.

        Args:
            user_id: Database user ID
            cooldown_days: Number of days to exclude recently learned words
            limit: Maximum number of words to select
            excluded_word_ids: Optional list of word IDs to exclude (e.g., already in selection)

        Returns:
            List of Vocabulary objects
        """
        cutoff_date = datetime.now() - timedelta(days=cooldown_days)

        query = self.db.query(Vocabulary).filter(
            Vocabulary.user_id == user_id,
            Vocabulary.in_learn.is_(True),
            or_(Vocabulary.last_learned.is_(None), Vocabulary.last_learned < cutoff_date),
        )

        # Exclude specific word IDs if provided
        if excluded_word_ids:
            query = query.filter(~Vocabulary.id.in_(excluded_word_ids))

        result = query.order_by(func.random()).limit(limit).all()
        return result

    def get_vocabulary_item_for_recall(self, item_id: int, user_id: int) -> Vocabulary:
        """Get a vocabulary item by ID and user_id, ensuring it's in learning."""
        vocab = (
            self.db.query(Vocabulary)
            .filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True))
            .first()
        )

        if not vocab:
            raise ValueError(f"Vocabulary item with id {item_id} not found for user {user_id} or not in learning")

        return vocab

    def get_vocabulary_items_by_ids(self, item_ids: List[int], user_id: int) -> List[Vocabulary]:
        """Get vocabulary items by IDs and user_id, ensuring they're in learning."""
        if not item_ids:
            return []
        return (
            self.db.query(Vocabulary)
            .filter(Vocabulary.id.in_(item_ids), Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True))
            .all()
        )

    def update_last_learned(self, vocab: Vocabulary) -> Vocabulary:
        """Update the last_learned timestamp and increment learned_times for a vocabulary item."""
        vocab.last_learned = datetime.now(timezone.utc)
        vocab.learned_times = (vocab.learned_times or 0) + 1
        return self.update_vocabulary_item(vocab)

    def get_vocabulary_item_by_word_phrase(self, word_phrase: str, user_id: int) -> Optional[Vocabulary]:
        """Get a vocabulary item by word_phrase and user_id."""
        return (
            self.db.query(Vocabulary)
            .filter(Vocabulary.word_phrase == word_phrase, Vocabulary.user_id == user_id)
            .first()
        )

    def delete_vocabulary_item_by_word_phrase(self, word_phrase: str, user_id: int) -> bool:
        """Mark a vocabulary item as not in learning (soft delete) by word phrase."""
        updated_rows = (
            self.db.query(Vocabulary)
            .filter(Vocabulary.word_phrase == word_phrase, Vocabulary.user_id == user_id)
            .update({"in_learn": False})
        )
        self.db.commit()
        return updated_rows > 0

    def delete_vocabulary_item(self, item_id: int, user_id: int) -> bool:
        """Mark a vocabulary item as not in learning (soft delete)."""
        updated_rows = (
            self.db.query(Vocabulary)
            .filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id)
            .update({"in_learn": False})
        )
        self.db.commit()
        return updated_rows > 0

    def hard_delete_vocabulary_item(self, item_id: int, user_id: int) -> bool:
        """Completely delete a vocabulary item from the database."""
        deleted_rows = (
            self.db.query(Vocabulary).filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id).delete()
        )
        self.db.commit()
        return deleted_rows > 0

    def get_words_in_learn_count(self, user_id: int) -> int:
        """Get count of vocabulary items with in_learn=True for a user."""
        return self.db.query(Vocabulary).filter(Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True)).count()

    def get_words_learned_count(self, user_id: int) -> int:
        """Get count of vocabulary items with in_learn=True AND learned_times > 0 for a user."""
        return (
            self.db.query(Vocabulary)
            .filter(Vocabulary.user_id == user_id, Vocabulary.in_learn.is_(True), Vocabulary.learned_times > 0)
            .count()
        )
