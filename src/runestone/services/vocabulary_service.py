"""
Service layer for vocabulary operations.

This module contains service classes that handle business logic
for vocabulary-related operations.
"""

from typing import List

from ..api.schemas import Vocabulary as VocabularySchema
from ..api.schemas import VocabularyItemCreate, VocabularyUpdate
from ..db.models import Vocabulary
from ..db.repository import VocabularyRepository


class VocabularyService:
    """Service for vocabulary-related business logic."""

    def __init__(self, vocabulary_repository: VocabularyRepository):
        """Initialize service with vocabulary repository."""
        self.repo = vocabulary_repository

    def save_vocabulary(self, items: List[VocabularyItemCreate], user_id: int = 1) -> dict:
        """Save vocabulary items, handling business logic."""
        # Get unique word_phrases from the batch
        batch_word_phrases = [item.word_phrase for item in items]

        # Get existing word_phrases for the user from this batch
        existing_word_phrases = self.repo.get_existing_word_phrases_for_batch(batch_word_phrases, user_id)

        # Filter items: remove duplicates within batch and existing in DB
        seen_in_batch = set()
        filtered_items = []

        for item in items:
            if item.word_phrase not in seen_in_batch and item.word_phrase not in existing_word_phrases:
                filtered_items.append(item)
                seen_in_batch.add(item.word_phrase)

        # Batch insert the filtered items
        if filtered_items:
            self.repo.batch_insert_vocabulary_items(filtered_items, user_id)

        return {"message": "Vocabulary saved successfully"}

    def get_vocabulary(self, limit: int, search_query: str | None = None, user_id: int = 1) -> List[VocabularySchema]:
        """Retrieve vocabulary items, optionally filtered by search query, converting to Pydantic models."""
        vocabularies = self.repo.get_vocabulary(limit, search_query, user_id)
        result = []
        for vocab in vocabularies:
            result.append(
                VocabularySchema(
                    id=vocab.id,
                    user_id=vocab.user_id,
                    word_phrase=vocab.word_phrase,
                    translation=vocab.translation,
                    example_phrase=vocab.example_phrase,
                    in_learn=vocab.in_learn,
                    last_learned=vocab.last_learned.isoformat() if vocab.last_learned else None,
                    created_at=vocab.created_at.isoformat() if vocab.created_at else None,
                    updated_at=vocab.updated_at.isoformat() if vocab.updated_at else None,
                )
            )
        return result

    def update_vocabulary_item(self, item_id: int, update: VocabularyUpdate, user_id: int = 1) -> VocabularySchema:
        """Update a vocabulary item and return the updated record."""
        vocab = self.repo.get_vocabulary_item(item_id, user_id)
        updates = update.model_dump(exclude_unset=True)
        allowed_fields = Vocabulary.UPDATABLE_FIELDS
        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                setattr(vocab, key, value)
        updated_vocab = self.repo.update_vocabulary_item(vocab)
        return VocabularySchema(
            id=updated_vocab.id,
            user_id=updated_vocab.user_id,
            word_phrase=updated_vocab.word_phrase,
            translation=updated_vocab.translation,
            example_phrase=updated_vocab.example_phrase,
            in_learn=updated_vocab.in_learn,
            last_learned=updated_vocab.last_learned.isoformat() if updated_vocab.last_learned else None,
            created_at=updated_vocab.created_at.isoformat() if updated_vocab.created_at else None,
            updated_at=updated_vocab.updated_at.isoformat() if updated_vocab.updated_at else None,
        )
