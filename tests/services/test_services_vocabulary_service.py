"""
Tests for vocabulary service functionality.

This module contains tests for the vocabulary service.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from runestone.api.schemas import ImprovementMode
from runestone.api.schemas import Vocabulary as VocabularySchema
from runestone.api.schemas import VocabularyImproveRequest, VocabularyImproveResponse, VocabularyItemCreate
from runestone.config import Settings
from runestone.core.exceptions import VocabularyItemExists
from runestone.db.models import Vocabulary as VocabularyModel
from runestone.services.vocabulary_service import VocabularyService


class TestVocabularyService:
    """Test cases for VocabularyService."""

    @pytest.fixture
    def service(self, vocabulary_repository):
        """Create a VocabularyService instance."""
        mock_settings = Mock(spec=Settings)
        mock_settings.llm_provider = "openai"
        mock_llm_client = Mock()
        # Set default mock response for LLM client to avoid TypeError
        mock_llm_client.improve_vocabulary_item.return_value = (
            '{"translation": "mock translation", "example_phrase": "mock example", "extra_info": "mock info"}'
        )
        return VocabularyService(vocabulary_repository, mock_settings, mock_llm_client)

    def test_save_vocabulary_new(self, service, db_session):
        """Test saving new vocabulary items."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),
        ]

        result = service.save_vocabulary(items, user_id=1, enrich=False)
        db_session.commit()

        assert result == {"message": "Vocabulary saved successfully"}

        # Verify items were added
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 2

        apple_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.user_id == 1
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None
        assert apple_vocab.learned_times == 0

    def test_save_vocabulary_duplicate(self, service, db_session):
        """Test that duplicate word_phrases are not added."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Ett äpple är rött."
            ),  # Same word_phrase
        ]

        result = service.save_vocabulary(items, user_id=1)
        db_session.commit()

        assert result == {"message": "Vocabulary saved successfully"}

        # Should only have one entry
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 1

        apple_vocab = vocabularies[0]
        assert apple_vocab.word_phrase == "ett äpple"
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None
        assert apple_vocab.learned_times == 0

    def test_get_vocabulary(self, service, db_session):
        """Test retrieving vocabulary items filtered by user."""
        # Add some test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            in_learn=True,
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=2, word_phrase="ett päron", translation="a pear", in_learn=True, last_learned=None
        )

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Get all for user 1
        result = service.get_vocabulary(user_id=1, limit=20)
        assert len(result) == 2
        assert isinstance(result[0], VocabularySchema)
        # Since timestamps are the same, order by id desc (most recent insertion first)
        assert result[0].word_phrase == "en banan"  # Higher id
        assert result[1].word_phrase == "ett äpple"  # Lower id

        # Get all for user 2
        result = service.get_vocabulary(user_id=2, limit=20)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"

    def test_get_vocabulary_recent(self, service, db_session):
        """Test retrieving vocabulary items sorted by creation date (most recent first)."""
        # Add test data with specific creation dates
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            in_learn=True,
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            in_learn=True,
            last_learned=None,
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3, vocab4])
        db_session.commit()

        # Get recent for user 1 (should return 3 items, most recent first)
        result = service.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 3
        assert isinstance(result[0], VocabularySchema)
        # Should be ordered by created_at descending
        assert result[0].word_phrase == "ett päron"  # Most recent
        assert result[1].word_phrase == "en banan"
        assert result[2].word_phrase == "ett äpple"  # Oldest

        # Test with limit
        result_limited = service.get_vocabulary(limit=2, user_id=1)
        assert len(result_limited) == 2
        assert result_limited[0].word_phrase == "ett päron"
        assert result_limited[1].word_phrase == "en banan"

        # Get recent for user 2 (should return 1 item)
        result_user2 = service.get_vocabulary(limit=20, user_id=2)
        assert len(result_user2) == 1
        assert result_user2[0].word_phrase == "en kiwi"

    def test_update_vocabulary_item(self, service, db_session):
        """Test updating a vocabulary item."""
        from runestone.api.schemas import VocabularyUpdate

        # Add a test item
        vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            last_learned=None,
        )
        db_session.add(vocab)
        db_session.commit()

        # Update the item
        update_data = VocabularyUpdate(
            word_phrase="ett rött äpple",
            translation="a red apple",
            in_learn=False,
        )
        updated_vocab = service.update_vocabulary_item(vocab.id, update_data, user_id=1)

        # Verify the update
        assert isinstance(updated_vocab, VocabularySchema)
        assert updated_vocab.word_phrase == "ett rött äpple"
        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_vocab.in_learn is False
        assert updated_vocab.last_learned is None  # Unchanged
        assert updated_vocab.learned_times == 0  # Unchanged

    def test_update_vocabulary_item_partial(self, service, db_session):
        """Test updating a vocabulary item with partial fields."""
        from runestone.api.schemas import VocabularyUpdate

        # Add a test item
        vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            last_learned=None,
        )
        db_session.add(vocab)
        db_session.commit()

        # Update only one field
        update_data = VocabularyUpdate(in_learn=False)
        updated_vocab = service.update_vocabulary_item(vocab.id, update_data, user_id=1)

        # Verify only in_learn changed
        assert updated_vocab.word_phrase == "ett äpple"
        assert updated_vocab.translation == "an apple"
        assert updated_vocab.in_learn is False

    def test_update_vocabulary_item_duplicate_word_phrase(self, service, db_session):
        """Test that updating to a duplicate word_phrase raises an error."""
        from runestone.api.schemas import VocabularyUpdate

        # Add two test items
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            in_learn=True,
            last_learned=None,
        )
        db_session.add_all([vocab1, vocab2])
        db_session.commit()

        # Try to update vocab1's word_phrase to match vocab2's word_phrase
        update_data = VocabularyUpdate(word_phrase="en banan")

        with pytest.raises(VocabularyItemExists, match="Vocabulary item with word_phrase 'en banan' already exists"):
            service.update_vocabulary_item(vocab1.id, update_data, user_id=1)

        # Verify vocab1 was not updated
        db_vocab1 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab1.id).first()
        assert db_vocab1.word_phrase == "ett äpple"
        assert db_vocab1.translation == "an apple"

        # Verify vocab2 remains unchanged
        db_vocab2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab2.id).first()
        assert db_vocab2.word_phrase == "en banan"
        assert db_vocab2.translation == "a banana"

    def test_save_vocabulary_item_new(self, service, db_session):
        """Test saving a new single vocabulary item."""
        item = VocabularyItemCreate(
            word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
        )

        result = service.save_vocabulary_item(item, user_id=1)
        db_session.commit()

        assert isinstance(result, VocabularySchema)
        assert result.word_phrase == "ett äpple"
        assert result.translation == "an apple"
        assert result.example_phrase == "Jag äter ett äpple varje dag."
        assert result.user_id == 1
        assert result.in_learn is True
        assert result.last_learned is None
        assert result.learned_times == 0

        # Verify item was added to DB
        vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert vocab is not None
        assert vocab.translation == "an apple"

    def test_save_vocabulary_item_duplicate(self, service, db_session):
        """Test that saving duplicate word_phrase raises an error."""
        # Pre-add an item
        existing_vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple.",
            in_learn=True,
        )
        db_session.add(existing_vocab)
        db_session.commit()
        existing_id = existing_vocab.id

        # Try to save same word_phrase
        item = VocabularyItemCreate(
            word_phrase="ett äpple", translation="an apple updated", example_phrase="Ett äpple är rött."
        )

        with pytest.raises(VocabularyItemExists, match="Vocabulary item with word_phrase 'ett äpple' already exists"):
            service.save_vocabulary_item(item, user_id=1)

        # Verify no new item was added and existing item remains unchanged
        vocabularies = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").all()
        assert len(vocabularies) == 1
        existing_vocab = vocabularies[0]
        assert existing_vocab.id == existing_id
        assert existing_vocab.translation == "an apple"
        assert existing_vocab.example_phrase == "Jag äter ett äpple."

    def test_save_vocabulary_item_without_example(self, service, db_session):
        """Test saving a vocabulary item without example phrase."""
        item = VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None)

        result = service.save_vocabulary_item(item, user_id=1)
        db_session.commit()

        assert isinstance(result, VocabularySchema)
        assert result.word_phrase == "en banan"
        assert result.translation == "a banana"
        assert result.example_phrase is None
        assert result.learned_times == 0

    def test_load_vocab_from_csv_skip_check(self, service, db_session):
        """Test loading vocabulary from CSV with skip existence check (upsert)."""
        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple updated", example_phrase="Ett äpple är rött."
            ),  # Duplicate in batch - will upsert last
        ]

        result = service.load_vocab_from_csv(items, skip_existence_check=True, user_id=1)
        db_session.commit()

        assert result == {
            "original_count": 3,
            "added_count": 3,  # All items processed (upsert)
            "skipped_count": 0,  # No skipping in upsert mode
        }

        # Verify items in DB
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 2  # ett äpple and en banan

        apple_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert apple_vocab.translation == "an apple updated"  # Last upsert wins
        assert apple_vocab.example_phrase == "Ett äpple är rött."

        banana_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "en banan").first()
        assert banana_vocab.translation == "a banana"

    def test_load_vocab_from_csv_with_check(self, service, db_session):
        """Test loading vocabulary from CSV with existence check (add only new)."""
        # Pre-add one item
        existing_vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple.",
            in_learn=True,
        )
        db_session.add(existing_vocab)
        db_session.commit()

        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple updated", example_phrase="Ett äpple är rött."
            ),  # Existing
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),  # New
            VocabularyItemCreate(word_phrase="ett päron", translation="a pear", example_phrase=None),  # New
            VocabularyItemCreate(
                word_phrase="ett päron", translation="a pear updated", example_phrase="Ett päron är gult."
            ),  # Duplicate in batch
        ]

        result = service.load_vocab_from_csv(items, skip_existence_check=False, user_id=1)
        db_session.commit()

        assert result == {
            "original_count": 4,
            "added_count": 2,  # en banan and ett päron (first occurrence)
            "skipped_count": 2,  # existing äpple and duplicate päron
        }

        # Verify items in DB
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 3  # Original + 2 new

        # Existing äpple unchanged
        apple_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple."

        # New items added
        banana_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "en banan").first()
        assert banana_vocab.translation == "a banana"

        pear_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett päron").first()
        assert pear_vocab.translation == "a pear"
        assert pear_vocab.example_phrase is None

    def test_delete_vocabulary_item(self, service, db_session):
        """Test hard deleting a vocabulary item."""
        # Add test items
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            in_learn=True,
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=2,
            word_phrase="ett päron",
            translation="a pear",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Verify initial count
        initial_count = db_session.query(VocabularyModel).count()
        assert initial_count == 3

        # Test successful deletion
        result = service.delete_vocabulary_item(vocab1.id, user_id=1)
        assert result is True

        # Verify item is completely removed from database
        db_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab1.id).first()
        assert db_vocab is None

        # Verify other items still exist
        remaining_count = db_session.query(VocabularyModel).count()
        assert remaining_count == 2

        # Verify other user's item is unchanged
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2 is not None
        assert db_vocab_user2.in_learn is True

        # Test deleting non-existent item
        result = service.delete_vocabulary_item(999, user_id=1)
        assert result is False

        # Test deleting with wrong user (should not delete)
        result = service.delete_vocabulary_item(vocab3.id, user_id=1)
        assert result is False

        # Verify user 2's item still exists
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2 is not None

    def test_improve_item_success(self, service):
        """Test successful vocabulary item improvement with ALL_FIELDS mode."""
        # Mock LLM client from the service fixture
        service.llm_client.improve_vocabulary_item.return_value = (
            '{"translation": "an apple", "example_phrase": "Jag äter ett äpple varje dag.", '
            '"extra_info": "en-word, noun"}'
        )

        # Test request with ALL_FIELDS mode
        request = VocabularyImproveRequest(word_phrase="ett äpple", mode=ImprovementMode.ALL_FIELDS)

        result = service.improve_item(request)

        # Verify result
        assert isinstance(result, VocabularyImproveResponse)
        assert result.translation == "an apple"
        assert result.example_phrase == "Jag äter ett äpple varje dag."
        assert result.extra_info == "en-word, noun"

        # Verify LLM client was called correctly
        service.llm_client.improve_vocabulary_item.assert_called_once()
        prompt_arg = service.llm_client.improve_vocabulary_item.call_args[0][0]
        assert "ett äpple" in prompt_arg

    def test_improve_item_without_translation(self, service):
        """Test vocabulary improvement with EXAMPLE_ONLY mode."""
        # Mock LLM client from the service fixture
        service.llm_client.improve_vocabulary_item.return_value = '{"example_phrase": "Jag äter ett äpple varje dag."}'

        # Test request with EXAMPLE_ONLY mode
        request = VocabularyImproveRequest(word_phrase="ett äpple", mode=ImprovementMode.EXAMPLE_ONLY)

        result = service.improve_item(request)

        # Verify result
        assert isinstance(result, VocabularyImproveResponse)
        assert result.translation is None
        assert result.example_phrase == "Jag äter ett äpple varje dag."
        assert result.extra_info is None

    def test_improve_item_malformed_response_handling(self, service):
        """Test vocabulary improvement with malformed LLM response that gets parsed gracefully."""

        # Mock LLM client from the service fixture
        service.llm_client.improve_vocabulary_item.return_value = (
            'translation: "clear", example_phrase: "Det är tydliga instruktioner.", extra_info: "adjective"'
        )

        # Test request with ALL_FIELDS mode
        request = VocabularyImproveRequest(word_phrase="tydliga", mode=ImprovementMode.ALL_FIELDS)

        result = service.improve_item(request)

        # Should handle malformed response gracefully and extract what it can
        assert isinstance(result, VocabularyImproveResponse)
        # The parser should extract "clear" from the translation field
        assert result.translation == "clear"
        # The parser should extract the example phrase from the example_phrase field
        assert result.example_phrase == "Det är tydliga instruktioner."
        # The parser should extract extra_info
        assert result.extra_info == "adjective"

    def test_improve_item_with_extra_info(self, service):
        """Test vocabulary improvement with ALL_FIELDS mode including extra_info."""
        # Mock LLM client from the service fixture
        service.llm_client.improve_vocabulary_item.return_value = (
            '{"translation": "an apple", "example_phrase": "Jag äter ett äpple varje dag.", '
            '"extra_info": "en-word, noun, base form: äpple"}'
        )

        # Test request with ALL_FIELDS mode
        request = VocabularyImproveRequest(word_phrase="ett äpple", mode=ImprovementMode.ALL_FIELDS)

        result = service.improve_item(request)

        # Verify result
        assert isinstance(result, VocabularyImproveResponse)
        assert result.translation == "an apple"
        assert result.example_phrase == "Jag äter ett äpple varje dag."
        assert result.extra_info == "en-word, noun, base form: äpple"

        # Verify LLM client was called correctly
        service.llm_client.improve_vocabulary_item.assert_called_once()
        prompt_arg = service.llm_client.improve_vocabulary_item.call_args[0][0]
        assert "ett äpple" in prompt_arg
        assert "extra_info" in prompt_arg

    def test_improve_item_extra_info_only(self, service):
        """Test vocabulary improvement with EXTRA_INFO_ONLY mode."""
        # Mock LLM client from the service fixture
        service.llm_client.improve_vocabulary_item.return_value = '{"extra_info": "en-word, noun, base form: äpple"}'

        # Test request with EXTRA_INFO_ONLY mode
        request = VocabularyImproveRequest(word_phrase="ett äpple", mode=ImprovementMode.EXTRA_INFO_ONLY)

        result = service.improve_item(request)

        # Verify result
        assert isinstance(result, VocabularyImproveResponse)
        assert result.translation is None
        assert result.example_phrase is None
        assert result.extra_info == "en-word, noun, base form: äpple"

    def test_enrich_vocabulary_items_success(self, service):
        """Test successful vocabulary items batch enrichment."""
        # Mock LLM client to return batch response
        service.llm_client.improve_vocabulary_batch.return_value = """
        {
            "ett äpple": "en-word, noun, base form: äpple",
            "en banan": "en-word, noun",
            "vara": "verb, forms: vara, är, var, varit"
        }
        """

        # Test items
        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase="Han äter en banan."),
            VocabularyItemCreate(word_phrase="vara", translation="to be", example_phrase="Jag vill vara glad."),
        ]

        # Enrich the items
        enriched_items = service._enrich_vocabulary_items(items)

        # Verify all enriched
        assert len(enriched_items) == 3
        assert enriched_items[0].extra_info == "en-word, noun, base form: äpple"
        assert enriched_items[1].extra_info == "en-word, noun"
        assert enriched_items[2].extra_info == "verb, forms: vara, är, var, varit"

    def test_enrich_vocabulary_items_llm_exception(self, service):
        """Test vocabulary items enrichment when LLM raises exception."""
        # Mock LLM to raise exception
        service.llm_client.improve_vocabulary_batch.side_effect = Exception("LLM error")

        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
        ]

        # Should not raise, but return items without enrichment
        enriched_items = service._enrich_vocabulary_items(items)

        assert len(enriched_items) == 1
        assert enriched_items[0].extra_info is None

    def test_save_vocabulary_items_with_enrichment(self, service, db_session):
        """Test saving vocabulary items with enrichment enabled."""
        # Mock LLM client
        service.llm_client.improve_vocabulary_batch.return_value = '{"ett äpple": "en-word, noun"}'

        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple.")
        ]

        # Save with enrichment
        result = service.save_vocabulary(items, user_id=1, enrich=True)
        db_session.commit()

        # Verify item was enriched - result is a dict with message
        assert result == {"message": "Vocabulary saved successfully"}

        # Verify extra_info was saved to database
        vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert vocab is not None
        assert vocab.extra_info == "en-word, noun"

    def test_save_vocabulary_items_without_enrichment(self, service, db_session):
        """Test saving vocabulary items with enrichment disabled."""
        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple.")
        ]

        # Save without enrichment
        result = service.save_vocabulary(items, user_id=1, enrich=False)

        # Verify item was not enriched - result is a dict with message
        assert result == {"message": "Vocabulary saved successfully"}
        service.llm_client.improve_vocabulary_batch.assert_not_called()

    def test_enrich_vocabulary_items_partial_failure(self, service):
        """Test vocabulary items batch enrichment with partial failures."""
        # Mock LLM with some null values
        service.llm_client.improve_vocabulary_batch.return_value = """
        {
            "ett äpple": "en-word, noun, base form: äpple",
            "en banan": null,
            "vara": "verb, forms: vara, är, var, varit"
        }
        """

        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase="Han äter en banan."),
            VocabularyItemCreate(word_phrase="vara", translation="to be", example_phrase="Jag vill vara glad."),
        ]

        enriched_items = service._enrich_vocabulary_items(items)

        # Verify: 2 enriched, 1 failed
        assert len(enriched_items) == 3
        assert enriched_items[0].extra_info == "en-word, noun, base form: äpple"
        assert enriched_items[1].extra_info is None  # Failed
        assert enriched_items[2].extra_info == "verb, forms: vara, är, var, varit"

    def test_enrich_vocabulary_items_large_batch(self, service):
        """Test vocabulary items enrichment with >100 items (multiple batches)."""
        # Create 150 items
        items = [
            VocabularyItemCreate(
                word_phrase=f"word_{i}", translation=f"translation_{i}", example_phrase=f"Example {i}."
            )
            for i in range(150)
        ]

        # Mock LLM to return appropriate responses for each batch
        def mock_batch_response(prompt):
            # Extract word count from prompt
            if "word_0" in prompt and "word_99" in prompt:
                # First batch (0-99)
                return "{" + ",".join(f'"word_{i}": "info_{i}"' for i in range(100)) + "}"
            else:
                # Second batch (100-149)
                return "{" + ",".join(f'"word_{i}": "info_{i}"' for i in range(100, 150)) + "}"

        service.llm_client.improve_vocabulary_batch.side_effect = mock_batch_response

        enriched_items = service._enrich_vocabulary_items(items)

        # Verify all 150 items enriched across 2 batches
        assert len(enriched_items) == 150
        assert all(item.extra_info for item in enriched_items)
        assert service.llm_client.improve_vocabulary_batch.call_count == 2

    def test_enrich_vocabulary_items_empty_list(self, service):
        """Test vocabulary items enrichment with empty list."""
        enriched_items = service._enrich_vocabulary_items([])

        assert enriched_items == []
        service.llm_client.improve_vocabulary_batch.assert_not_called()

    def test_save_vocabulary_with_batch_enrichment(self, service, db_session):
        """Test save_vocabulary using batch enrichment."""
        # Mock batch enrichment
        service.llm_client.improve_vocabulary_batch.return_value = """
        {
            "ett äpple": "en-word, noun, base form: äpple"
        }
        """

        items = [
            VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple.")
        ]

        result = service.save_vocabulary(items, user_id=1, enrich=True)
        db_session.commit()

        # Verify result
        assert result == {"message": "Vocabulary saved successfully"}

        # Verify item saved with enrichment
        vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert vocab is not None
        assert vocab.extra_info == "en-word, noun, base form: äpple"
        service.llm_client.improve_vocabulary_item.assert_not_called()

    def test_get_existing_word_phrases(self, service, db_session):
        """Test retrieving existing word phrases."""
        # Add some test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            in_learn=True,
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=2,
            word_phrase="ett päron",
            translation="a pear",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Test for user 1
        word_phrases_to_check = ["ett äpple", "en banan", "en apelsin"]
        existing = service.get_existing_word_phrases(word_phrases_to_check, user_id=1)
        assert sorted(existing) == sorted(["ett äpple", "en banan"])

        # Test for user 2
        word_phrases_to_check = ["ett päron", "en banan"]
        existing = service.get_existing_word_phrases(word_phrases_to_check, user_id=2)
        assert existing == ["ett päron"]

        # Test with no existing phrases
        word_phrases_to_check = ["en apelsin", "en druva"]
        existing = service.get_existing_word_phrases(word_phrases_to_check, user_id=1)

    def test_get_vocabulary_with_precise_flag(self, service, db_session):
        """Test that service passes through precise flag correctly."""
        from unittest.mock import patch

        # Add test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="apple",
            translation="äpple",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="pineapple",
            translation="ananas",
            in_learn=True,
            last_learned=None,
        )
        db_session.add_all([vocab1, vocab2])
        db_session.commit()

        # Test with precise=False (partial search)
        with patch.object(service.repo, "get_vocabulary") as mock_repo:
            mock_repo.return_value = [vocab1, vocab2]
            result = service.get_vocabulary(user_id=1, limit=20, search_query="apple", precise=False)

            # Verify repo called with precise=False
            mock_repo.assert_called_once_with(1, 20, "apple", False)
            assert len(result) == 2

        # Test with precise=True (exact search)
        with patch.object(service.repo, "get_vocabulary") as mock_repo:
            mock_repo.return_value = [vocab1]
            result = service.get_vocabulary(limit=20, search_query="apple", precise=True, user_id=1)

            # Verify repo called with precise=True
            mock_repo.assert_called_once_with(1, 20, "apple", True)
            assert len(result) == 1

        # Test default precise=False when not specified
        with patch.object(service.repo, "get_vocabulary") as mock_repo:
            mock_repo.return_value = [vocab1, vocab2]
            result = service.get_vocabulary(limit=20, search_query="apple", user_id=1)

            # Verify repo called with precise=False (default)
            mock_repo.assert_called_once_with(1, 20, "apple", False)
            assert len(result) == 2
