"""
Service layer for vocabulary operations.

This module contains service classes that handle business logic
for vocabulary-related operations.
"""

from typing import List

from ..api.schemas import Vocabulary as VocabularySchema
from ..api.schemas import VocabularyImproveRequest, VocabularyImproveResponse, VocabularyItemCreate, VocabularyUpdate
from ..config import Settings
from ..core.clients.base import BaseLLMClient
from ..core.constants import VOCABULARY_BATCH_SIZE
from ..core.exceptions import VocabularyItemExists
from ..core.logging_config import get_logger
from ..core.prompt_builder.builder import PromptBuilder
from ..core.prompt_builder.exceptions import ResponseParseError
from ..core.prompt_builder.parsers import ResponseParser
from ..db.models import Vocabulary
from ..db.repository import VocabularyRepository


class VocabularyService:
    """Service for vocabulary-related business logic."""

    def __init__(self, vocabulary_repository: VocabularyRepository, settings: Settings, llm_client: BaseLLMClient):
        """Initialize service with vocabulary repository, settings, and LLM client."""
        self.repo = vocabulary_repository
        self.settings = settings
        self.llm_client = llm_client
        self.logger = get_logger(__name__)

        # Initialize prompt builder and parser
        self.builder = PromptBuilder()
        self.parser = ResponseParser()

    def save_vocabulary(self, items: List[VocabularyItemCreate], enrich: bool = True, user_id: int = 1) -> dict:
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

        # Enrich filtered items if requested (CHANGED: now uses batch method)
        if enrich and filtered_items:
            filtered_items = self._enrich_vocabulary_items(filtered_items)

        # Batch insert the filtered (and potentially enriched) items
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
            extra_info=vocab.extra_info,
            in_learn=vocab.in_learn,
            last_learned=vocab.last_learned.isoformat() if vocab.last_learned else None,
            created_at=vocab.created_at.isoformat() if vocab.created_at else None,
            updated_at=vocab.updated_at.isoformat() if vocab.updated_at else None,
        )

    def get_vocabulary(
        self, limit: int, search_query: str | None = None, precise: bool = False, user_id: int = 1
    ) -> List[VocabularySchema]:
        """Retrieve vocabulary items, optionally filtered by search query, converting to Pydantic models."""
        vocabularies = self.repo.get_vocabulary(limit, search_query, precise, user_id)
        result = []
        for vocab in vocabularies:
            result.append(
                VocabularySchema(
                    id=vocab.id,
                    user_id=vocab.user_id,
                    word_phrase=vocab.word_phrase,
                    translation=vocab.translation,
                    example_phrase=vocab.example_phrase,
                    extra_info=vocab.extra_info,
                    in_learn=vocab.in_learn,
                    last_learned=vocab.last_learned.isoformat() if vocab.last_learned else None,
                    learned_times=vocab.learned_times or 0,
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
                raise VocabularyItemExists(
                    f"Vocabulary item with word_phrase '{updates['word_phrase']}' already exists"
                )

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
            extra_info=updated_vocab.extra_info,
            in_learn=updated_vocab.in_learn,
            last_learned=updated_vocab.last_learned.isoformat() if updated_vocab.last_learned else None,
            learned_times=updated_vocab.learned_times or 0,
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
        """Improve a vocabulary item using LLM to generate translation, example phrase, and extra info."""
        # Build improvement prompt using PromptBuilder
        prompt = self.builder.build_vocabulary_prompt(word_phrase=request.word_phrase, mode=request.mode)

        # Get improvement from LLM
        response_text = self.llm_client.improve_vocabulary_item(prompt)

        # Parse response using ResponseParser (includes automatic fallback)
        try:
            vocab_response = self.parser.parse_vocabulary_response(response_text, request.mode)

            return VocabularyImproveResponse(
                translation=vocab_response.translation,
                example_phrase=vocab_response.example_phrase,
                extra_info=vocab_response.extra_info,
            )
        except ResponseParseError as e:
            self.logger.error(f"Failed to parse vocabulary response: {e}")
            # Return empty response as fallback
            return VocabularyImproveResponse(translation=None, example_phrase="", extra_info=None)

    def _enrich_vocabulary_items(self, items: List[VocabularyItemCreate]) -> List[VocabularyItemCreate]:
        """
        Enrich vocabulary items with extra_info using LLM batch processing.

        Processes items in batches of up to 100 for optimal performance.
        Handles partial failures gracefully - enriches successful items and logs failures.

        Args:
            items: List of vocabulary items to enrich

        Returns:
            List of vocabulary items with extra_info populated where successful
        """
        if not items:
            return items

        enriched_items = []
        total_enriched = 0
        total_failed = 0

        # Process in batches
        for batch_start in range(0, len(items), VOCABULARY_BATCH_SIZE):
            batch_end = min(batch_start + VOCABULARY_BATCH_SIZE, len(items))
            batch = items[batch_start:batch_end]
            batch_num = batch_start // VOCABULARY_BATCH_SIZE + 1

            try:
                # Extract word_phrases for this batch
                word_phrases = [item.word_phrase for item in batch]

                # Build batch prompt
                prompt = self.builder.build_vocabulary_batch_prompt(word_phrases)

                # Get batch improvements from LLM
                response_text = self.llm_client.improve_vocabulary_batch(prompt)

                # Parse batch response
                enrichments = self.parser.parse_vocabulary_batch_response(response_text)

                # Apply enrichments to items
                batch_success = 0
                batch_failed = 0

                for item in batch:
                    extra_info = enrichments.get(item.word_phrase)

                    # Create enriched item
                    enriched_item = VocabularyItemCreate(
                        word_phrase=item.word_phrase,
                        translation=item.translation,
                        example_phrase=item.example_phrase,
                        extra_info=extra_info if extra_info else item.extra_info,
                        in_learn=item.in_learn,
                    )
                    enriched_items.append(enriched_item)

                    if extra_info:
                        batch_success += 1
                    else:
                        batch_failed += 1

                total_enriched += batch_success
                total_failed += batch_failed

                if batch_failed > 0:
                    self.logger.warning(
                        f"Batch {batch_num}: {batch_success} items enriched, {batch_failed} items failed"
                    )
                else:
                    self.logger.info(f"Batch {batch_num}: All {batch_success} items enriched successfully")

            except Exception as e:
                # Log error but continue with non-enriched items
                self.logger.error(f"Failed to enrich batch {batch_num}: {e}")
                # Add items without enrichment
                enriched_items.extend(batch)
                total_failed += len(batch)

        # Log summary
        total_items = len(items)
        self.logger.info(
            f"Enrichment summary: {total_enriched}/{total_items} successful, {total_failed}/{total_items} failed"
        )

        return enriched_items

    def get_existing_word_phrases(self, word_phrases: List[str], user_id: int) -> List[str]:
        """Get existing word phrases from the repository."""
        return list(self.repo.get_existing_word_phrases_for_batch(word_phrases, user_id))

    def delete_vocabulary_item(self, item_id: int, user_id: int = 1) -> bool:
        """Completely delete a vocabulary item from the database."""
        return self.repo.hard_delete_vocabulary_item(item_id, user_id)
