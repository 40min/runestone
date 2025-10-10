"""
Service layer for vocabulary operations.

This module contains service classes that handle business logic
for vocabulary-related operations.
"""

import json
import re
from typing import List

from ..api.schemas import Vocabulary as VocabularySchema
from ..api.schemas import VocabularyImproveRequest, VocabularyImproveResponse, VocabularyItemCreate, VocabularyUpdate
from ..config import Settings
from ..core.clients.base import BaseLLMClient
from ..core.exceptions import VocabularyItemExists
from ..core.logging_config import get_logger
from ..core.prompts import VOCABULARY_IMPROVE_PROMPT_TEMPLATE
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
            extra_info=vocab.extra_info,
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
        prompt = self._build_improvement_prompt(request)

        # Get improvement from LLM
        response_text = self.llm_client.improve_vocabulary_item(prompt)

        # Parse JSON response with fallback for malformed responses
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse LLM response as JSON: {response_text}. Error: {e}")
            # Try to extract information from malformed response
            result = self._parse_malformed_llm_response(
                response_text, request.include_translation, request.include_extra_info
            )

        translation = result.get("translation") if request.include_translation else None
        example_phrase = result.get("example_phrase", "")
        extra_info = result.get("extra_info") if request.include_extra_info else None

        return VocabularyImproveResponse(translation=translation, example_phrase=example_phrase, extra_info=extra_info)

    def _build_improvement_prompt(self, request: VocabularyImproveRequest) -> str:
        """Build the LLM prompt for vocabulary improvement."""
        # Prepare content type description
        content_parts = []
        if request.include_translation:
            content_parts.append("translation")
        if request.include_extra_info:
            content_parts.append("extra info")
        content_parts.append("example phrase")  # Always include example phrase

        content_type = (
            ", ".join(content_parts[:-1]) + " and " + content_parts[-1] if len(content_parts) > 1 else content_parts[0]
        )

        # Build JSON schema field for translation
        if request.include_translation:
            translation_instruction_json = '"English translation of the word/phrase"'
            translation_detail = "Provide the most common and accurate English translation."
        else:
            translation_instruction_json = "null"
            translation_detail = "Set translation to null since only example phrase is requested."

        # Build JSON schema field and instructions for extra_info
        if request.include_extra_info:
            extra_info_json = (
                ',\n    "extra_info": "A concise description of grammatical details '
                '(e.g., word form, base form, en/ett classification)"'
            )
            extra_info_detail = """

3. For extra_info:
    - Provide grammatical information about the Swedish word/phrase
    - Include word form (noun, verb, adjective, etc.), en/ett classification for nouns, base forms, etc.
    - Keep it concise and human-readable (e.g., "en-word, noun, base form: ord")
    - Focus on the most important grammatical details for language learners"""
        else:
            extra_info_json = ""
            extra_info_detail = ""

        # Build the complete prompt
        return VOCABULARY_IMPROVE_PROMPT_TEMPLATE.format(
            word_phrase=request.word_phrase,
            content_type=content_type,
            translation_instruction_json=translation_instruction_json,
            translation_detail=translation_detail,
            extra_info_json=extra_info_json,
            extra_info_detail=extra_info_detail,
        )

    def delete_vocabulary_item(self, item_id: int, user_id: int = 1) -> bool:
        """Completely delete a vocabulary item from the database."""
        return self.repo.hard_delete_vocabulary_item(item_id, user_id)

    def _parse_malformed_llm_response(
        self, response_text: str, include_translation: bool, include_extra_info: bool = False
    ) -> dict:
        """
        Parse a malformed LLM response that is not valid JSON.

        Attempts to extract translation, example_phrase, and extra_info from various formats.
        Returns a dict with 'translation', 'example_phrase', and 'extra_info' keys.
        """

        result = {"translation": None, "example_phrase": "", "extra_info": None}

        # Clean the response text
        response_text = response_text.strip()

        # Try to find JSON-like structure even if malformed
        if response_text.startswith("{") and response_text.endswith("}"):
            # Try to fix common JSON issues
            fixed_text = response_text
            # Fix trailing commas
            fixed_text = re.sub(r",(\s*[}\]])", r"\1", fixed_text)
            # Fix missing quotes around keys
            fixed_text = re.sub(r"(\w+):", r'"\1":', fixed_text)
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass  # Continue with other parsing methods

        # Try to extract using regex patterns
        # Look for translation: "value" (with or without quotes around key)
        translation_match = re.search(r'(?:"translation"|\btranslation)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
        if translation_match:
            result["translation"] = translation_match.group(1)

        # Look for example_phrase: "value" (with or without quotes around key)
        example_match = re.search(
            r'(?:"example_phrase"|\bexample_phrase)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE
        )
        if example_match:
            result["example_phrase"] = example_match.group(1)

        # Look for extra_info: "value" (with or without quotes around key)
        if include_extra_info:
            extra_info_match = re.search(r'(?:"extra_info"|\bextra_info)\s*:\s*"([^"]*)"', response_text, re.IGNORECASE)
            if extra_info_match:
                result["extra_info"] = extra_info_match.group(1)

        # If no structured data found, try to extract from plain text
        if not result["translation"] and not result["example_phrase"] and not result["extra_info"]:
            # Split by common separators and take the first meaningful part as example
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]
            if lines:
                # Assume the first line is the example phrase
                result["example_phrase"] = lines[0]

        # If translation was requested but not found, try to infer it
        if include_translation and not result["translation"]:
            # Look for English words that might be translations
            words = re.findall(r"\b[a-zA-Z]+\b", response_text)
            english_words = [
                w
                for w in words
                if len(w) > 2
                and w.lower()
                not in [
                    "the",
                    "and",
                    "for",
                    "are",
                    "but",
                    "not",
                    "you",
                    "all",
                    "can",
                    "had",
                    "her",
                    "was",
                    "one",
                    "our",
                    "out",
                    "day",
                    "get",
                    "has",
                    "him",
                    "his",
                    "how",
                    "its",
                    "may",
                    "new",
                    "now",
                    "old",
                    "see",
                    "two",
                    "way",
                    "who",
                    "boy",
                    "did",
                    "has",
                    "let",
                    "put",
                    "say",
                    "she",
                    "too",
                    "use",
                ]
            ]
            if english_words:
                result["translation"] = " ".join(english_words[:3])  # Take first few words

        return result
