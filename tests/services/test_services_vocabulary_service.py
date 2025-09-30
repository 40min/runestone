"""
Tests for vocabulary service functionality.

This module contains tests for the vocabulary service.
"""

import pytest

from runestone.api.schemas import Vocabulary as VocabularySchema
from runestone.api.schemas import VocabularyItemCreate
from runestone.db.models import Vocabulary as VocabularyModel
from runestone.services.vocabulary_service import VocabularyService


class TestVocabularyService:
    """Test cases for VocabularyService."""

    @pytest.fixture
    def service(self, vocabulary_repository):
        """Create a VocabularyService instance."""
        return VocabularyService(vocabulary_repository)

    def test_save_vocabulary_new(self, service, db_session):
        """Test saving new vocabulary items."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),
        ]

        result = service.save_vocabulary(items)
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

        result = service.save_vocabulary(items)
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

    def test_get_vocabulary(self, service, db_session):
        """Test retrieving all vocabulary items."""
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
        result = service.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 2
        assert isinstance(result[0], VocabularySchema)
        # Since timestamps are the same, order by id desc (most recent insertion first)
        assert result[0].word_phrase == "en banan"  # Higher id
        assert result[1].word_phrase == "ett äpple"  # Lower id

        # Get all for user 2
        result = service.get_vocabulary(limit=20, user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"

    def test_get_vocabulary_recent(self, service, db_session):
        """Test retrieving the most recent vocabulary items."""
        from datetime import datetime, timezone

        # Add test data with different creation times
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
        updated_vocab = service.update_vocabulary_item(vocab.id, update_data)

        # Verify the update
        assert isinstance(updated_vocab, VocabularySchema)
        assert updated_vocab.word_phrase == "ett rött äpple"
        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_vocab.in_learn is False
        assert updated_vocab.last_learned is None  # Unchanged

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
        updated_vocab = service.update_vocabulary_item(vocab.id, update_data)

        # Verify only in_learn changed
        assert updated_vocab.word_phrase == "ett äpple"
        assert updated_vocab.translation == "an apple"
        assert updated_vocab.in_learn is False

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

        # Verify item was added to DB
        vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert vocab is not None
        assert vocab.translation == "an apple"

    def test_save_vocabulary_item_duplicate(self, service, db_session):
        """Test that saving duplicate word_phrase returns existing item."""
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

        result = service.save_vocabulary_item(item, user_id=1)
        db_session.commit()

        # Should return existing item, not create new one
        assert isinstance(result, VocabularySchema)
        assert result.id == existing_id
        assert result.word_phrase == "ett äpple"
        # Should keep original values
        assert result.translation == "an apple"
        assert result.example_phrase == "Jag äter ett äpple."

        # Verify only one item exists in DB
        vocabularies = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").all()
        assert len(vocabularies) == 1

    def test_save_vocabulary_item_without_example(self, service, db_session):
        """Test saving a vocabulary item without example phrase."""
        item = VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None)

        result = service.save_vocabulary_item(item, user_id=1)
        db_session.commit()

        assert isinstance(result, VocabularySchema)
        assert result.word_phrase == "en banan"
        assert result.translation == "a banana"
        assert result.example_phrase is None

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
