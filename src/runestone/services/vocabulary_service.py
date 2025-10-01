"""
Service layer for vocabulary operations.

This module contains service classes that handle business logic
for vocabulary-related operations.
"""

from typing import List
import json

from ..api.schemas import Vocabulary as VocabularySchema
from ..api.schemas import VocabularyImproveRequest, VocabularyImproveResponse, VocabularyItemCreate, VocabularyUpdate
from ..config import Settings
from ..core.clients.factory import create_llm_client
from ..core.exceptions import VocabularyItemExists
from ..core.prompts import VOCABULARY_IMPROVE_PROMPT_TEMPLATE
from ..db.models import Vocabulary
from ..db.repository import VocabularyRepository


class VocabularyService:
    """Service for vocabulary-related business logic."""

    def __init__(self, vocabulary_repository: VocabularyRepository, settings: Settings):
        """Initialize service with vocabulary repository and settings."""
        self.repo = vocabulary_repository
        self.settings = settings

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

    def save_vocabulary_item(self, item: VocabularyItemCreate, user_id: int = 1) -> VocabularySchema:
        """Save a single vocabulary item, handling business logic."""
        # Check if the word_phrase already exists for the user
        existing = self.repo.get_existing_word_phrases_for_batch([item.word_phrase], user_id)
        if existing:
            raise VocabularyItemExists(f"Vocabulary item with word_phrase '{item.word_phrase}' already exists")

        # Insert the new item
        vocab = self.repo.insert_vocabulary_item(item, user_id)
        return VocabularySchema(
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

        # Check for duplicate word_phrase if it's being updated
        if "word_phrase" in updates and updates["word_phrase"] != vocab.word_phrase:
            existing = self.repo.get_existing_word_phrases_for_batch([updates["word_phrase"]], user_id)
            if existing:
                raise VocabularyItemExists(f"Vocabulary item with word_phrase '{updates['word_phrase']}' already exists")

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

    def load_vocab_from_csv(
        self, items: List[VocabularyItemCreate], skip_existence_check: bool, user_id: int = 1
    ) -> dict:
        """Load vocabulary items from CSV data, handling parsing, filtering, and insertion logic."""
        original_count = len(items)

        if skip_existence_check:
            # Upsert all items (update if exists, insert if not) - no filtering
            self.repo.upsert_vocabulary_items(items, user_id)
            added_count = len(items)
            skipped_count = 0  # No skipping in upsert mode
        else:
            # Filter duplicates within the batch
            seen = set()
            filtered_items = []
            for item in items:
                if item.word_phrase not in seen:
                    filtered_items.append(item)
                    seen.add(item.word_phrase)
            items = filtered_items

            # Get existing word_phrases before insertion
            batch_word_phrases = [item.word_phrase for item in items]
            existing_word_phrases = self.repo.get_existing_word_phrases_for_batch(batch_word_phrases, user_id)

            # Filter items: remove existing in DB
            final_items = [item for item in items if item.word_phrase not in existing_word_phrases]

            # Batch insert the filtered items
            if final_items:
                self.repo.batch_insert_vocabulary_items(final_items, user_id)

            added_count = len(final_items)
            skipped_count = original_count - added_count

        return {"original_count": original_count, "added_count": added_count, "skipped_count": skipped_count}

    def improve_item(self, request: VocabularyImproveRequest) -> VocabularyImproveResponse:
        """Improve a vocabulary item using LLM to generate translation and example phrase."""        

        # Create LLM client
        llm_client = create_llm_client(self.settings)

        # Prepare prompt parameters
        if request.include_translation:
            content_type = "both translation and example phrase"
            translation_instruction = '"English translation of the word/phrase"'
            translation_detail = "Provide the most common and accurate English translation."
        else:
            content_type = "an example phrase"
            translation_instruction = "null"
            translation_detail = "Set translation to null since only example phrase is requested."

        # Format the prompt with all required parameters
        prompt = VOCABULARY_IMPROVE_PROMPT_TEMPLATE.format(
            word_phrase=request.word_phrase,
            content_type=content_type,
            translation_instruction=translation_instruction,
            translation_detail=translation_detail
        )

        # Get improvement from LLM
        response_text = llm_client.improve_vocabulary_item(prompt)

        # Parse JSON response
        result = json.loads(response_text)
        translation = result.get("translation") if request.include_translation else None
        example_phrase = result.get("example_phrase", "")

        return VocabularyImproveResponse(
            translation=translation,
            example_phrase=example_phrase
        )

    def delete_vocabulary_item(self, item_id: int, user_id: int = 1) -> bool:
        """Completely delete a vocabulary item from the database."""
        return self.repo.hard_delete_vocabulary_item(item_id, user_id)
