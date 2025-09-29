"""
Repository classes for database operations.

This module contains repository classes that encapsulate database
logic for different entities.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, or_
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..api.schemas import VocabularyItemCreate
from .models import Vocabulary


class VocabularyRepository:
    """Repository for vocabulary-related database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_existing_word_phrases_for_batch(self, word_phrases: List[str], user_id: int = 1) -> set[str]:
        """Get existing word_phrases for a user from the given batch."""
        if not word_phrases:
            return set()
        result = (
            self.db.query(Vocabulary.word_phrase)
            .filter(Vocabulary.user_id == user_id, Vocabulary.word_phrase.in_(word_phrases))
            .all()
        )
        return {row[0] for row in result}

    def batch_insert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int = 1):
        """Batch insert vocabulary items (assumes duplicates are already filtered)."""
        vocab_objects = [
            Vocabulary(
                user_id=user_id,
                word_phrase=item.word_phrase,
                translation=item.translation,
                example_phrase=item.example_phrase,
                in_learn=True,
                last_learned=None,
            )
            for item in items
        ]
        self.db.add_all(vocab_objects)
        self.db.commit()

    def upsert_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int = 1):
        """Upsert vocabulary items: update if exists, insert if not."""
        if not items:
            return

        data = [
            {
                "user_id": user_id,
                "word_phrase": item.word_phrase,
                "translation": item.translation,
                "example_phrase": item.example_phrase,
                "in_learn": True,
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

    def add_vocabulary_items(self, items: List[VocabularyItemCreate], user_id: int = 1):
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

    def get_vocabulary(self, limit: int, search_query: str | None = None, user_id: int = 1) -> List[Vocabulary]:
        """Retrieve vocabulary items for a user, optionally filtered by search query."""
        query = self.db.query(Vocabulary).filter(Vocabulary.user_id == user_id)

        if search_query:
            # Support wildcard (*) pattern matching, case-insensitive
            search_pattern = search_query.replace("*", "%").lower()
            query = query.filter(Vocabulary.word_phrase.ilike(f"%{search_pattern}%"))

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

    def select_new_daily_word_ids(self, user_id: int, cooldown_days: int = 7) -> List[int]:
        """Select new daily word IDs for a user randomly, excluding recently learned words."""
        cutoff_date = datetime.now() - timedelta(days=cooldown_days)
        result = (
            self.db.query(Vocabulary.id)
            .filter(
                Vocabulary.user_id == user_id,
                Vocabulary.in_learn.is_(True),
                or_(Vocabulary.last_learned.is_(None), Vocabulary.last_learned < cutoff_date),
            )
            .order_by(func.random())
            .all()
        )
        return [row[0] for row in result]

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
        """Update the last_learned timestamp for a vocabulary item."""
        vocab.last_learned = datetime.now()
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
