"""
Repository classes for database operations.

This module contains repository classes that encapsulate database
logic for different entities.
"""

from typing import List

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
                showed_times=0,
            )
            for item in items
        ]
        self.db.add_all(vocab_objects)
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

    def update_vocabulary_item(self, item_id: int, user_id: int, updates: dict) -> Vocabulary:
        """Update a vocabulary item by ID and user_id."""
        vocab = self.db.query(Vocabulary).filter(Vocabulary.id == item_id, Vocabulary.user_id == user_id).first()

        if not vocab:
            raise ValueError(f"Vocabulary item with id {item_id} not found for user {user_id}")

        for key, value in updates.items():
            if value is not None:
                setattr(vocab, key, value)

        self.db.commit()
        self.db.refresh(vocab)
        return vocab
