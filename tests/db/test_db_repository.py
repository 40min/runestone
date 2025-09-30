"""
Tests for vocabulary database repository functionality.

This module contains tests for the vocabulary repository.
"""

from datetime import datetime, timedelta

import pytest

from runestone.api.schemas import VocabularyItemCreate
from runestone.db.models import Vocabulary as VocabularyModel


class TestVocabularyRepository:
    """Test cases for VocabularyRepository."""

    @pytest.fixture
    def repo(self, vocabulary_repository):
        """Create a VocabularyRepository instance."""
        return vocabulary_repository

    def test_add_vocabulary_items_new(self, repo, db_session):
        """Test adding new vocabulary items."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),
        ]

        repo.add_vocabulary_items(items)
        db_session.commit()

        # Verify items were added
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 2

        apple_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.user_id == 1
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None

    def test_add_vocabulary_items_duplicate(self, repo, db_session):
        """Test that duplicate word_phrases are not added."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Ett äpple är rött."
            ),  # Same word_phrase
        ]

        repo.add_vocabulary_items(items)
        db_session.commit()

        # Should only have one entry
        vocabularies = db_session.query(VocabularyModel).all()
        assert len(vocabularies) == 1

        apple_vocab = vocabularies[0]
        assert apple_vocab.word_phrase == "ett äpple"
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None

    def test_upsert_vocabulary_items(self, repo, db_session):
        """Test upserting vocabulary items (bulk insert/update)."""
        # Add an initial item
        initial_vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            last_learned=None,
        )
        db_session.add(initial_vocab)
        db_session.commit()

        # Record initial updated_at
        initial_updated_at = initial_vocab.updated_at

        # Upsert: update existing and add new
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple",  # Existing - should update
                translation="a red apple",  # Changed
                example_phrase="Ett äpple är rött.",  # Changed
            ),
            VocabularyItemCreate(
                word_phrase="en banan",  # New - should insert
                translation="a banana",
                example_phrase=None,
            ),
        ]

        repo.upsert_vocabulary_items(items)
        db_session.commit()

        # Verify existing item was updated
        updated_vocab = (
            db_session.query(VocabularyModel)
            .filter(VocabularyModel.word_phrase == "ett äpple", VocabularyModel.user_id == 1)
            .first()
        )
        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Ett äpple är rött."
        assert updated_vocab.in_learn is True  # Unchanged
        assert updated_vocab.updated_at > initial_updated_at  # Should be updated

        # Verify new item was inserted
        new_vocab = (
            db_session.query(VocabularyModel)
            .filter(VocabularyModel.word_phrase == "en banan", VocabularyModel.user_id == 1)
            .first()
        )
        assert new_vocab.translation == "a banana"
        assert new_vocab.example_phrase is None
        assert new_vocab.in_learn is True
        assert new_vocab.last_learned is None

        # Verify total count
        all_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.user_id == 1).all()
        assert len(all_vocab) == 2

    def test_get_all_vocabulary(self, repo, db_session):
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

        # Get all for user 1 (should return most recent first)
        result = repo.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 2
        # Since we didn't set created_at explicitly, they will be in insertion order
        # But the method should still work
        assert result[0].word_phrase in ["ett äpple", "en banan"]
        assert result[1].word_phrase in ["ett äpple", "en banan"]

        # Get all for user 2
        result = repo.get_vocabulary(limit=20, user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"

    def test_get_vocabulary_recent(self, repo, db_session):
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
        result = repo.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 3
        # Should be ordered by created_at descending
        assert result[0].word_phrase == "ett päron"  # Most recent
        assert result[1].word_phrase == "en banan"
        assert result[2].word_phrase == "ett äpple"  # Oldest

        # Test with limit
        result_limited = repo.get_vocabulary(limit=2, user_id=1)
        assert len(result_limited) == 2
        assert result_limited[0].word_phrase == "ett päron"
        assert result_limited[1].word_phrase == "en banan"

        # Get recent for user 2 (should return 1 item)
        result_user2 = repo.get_vocabulary(limit=20, user_id=2)
        assert len(result_user2) == 1
        assert result_user2[0].word_phrase == "en kiwi"

    def test_get_vocabulary_with_search(self, repo, db_session):
        """Test retrieving vocabulary items filtered by search query."""
        from datetime import datetime, timezone

        # Add test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
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

        # Search for "banan" - should find one match
        result = repo.get_vocabulary(limit=20, search_query="banan", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search for "ett" - should find two matches (äpple and päron), most recent first
        result = repo.get_vocabulary(limit=20, search_query="ett", user_id=1)
        assert len(result) == 2
        assert result[0].word_phrase == "ett päron"  # Most recent
        assert result[1].word_phrase == "ett äpple"

        # Search with wildcard "*" - "ban*" should match "banan"
        result = repo.get_vocabulary(limit=20, search_query="ban*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search case-insensitive - "BANAN" should match "banan"
        result = repo.get_vocabulary(limit=20, search_query="BANAN", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search for non-existent term
        result = repo.get_vocabulary(limit=20, search_query="xyz", user_id=1)
        assert len(result) == 0

        # Search for user 2
        result = repo.get_vocabulary(limit=20, search_query="kiwi", user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "en kiwi"

        # Test with limit
        result = repo.get_vocabulary(limit=1, search_query="ett", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"  # Most recent

    def test_get_vocabulary_item(self, repo, db_session):
        """Test getting a vocabulary item."""
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

        # Get the item
        retrieved_vocab = repo.get_vocabulary_item(vocab.id, user_id=1)

        # Verify
        assert retrieved_vocab.id == vocab.id
        assert retrieved_vocab.word_phrase == "ett äpple"
        assert retrieved_vocab.translation == "an apple"

    def test_get_vocabulary_item_not_found(self, repo, db_session):
        """Test getting a non-existent vocabulary item."""
        with pytest.raises(ValueError, match="Vocabulary item with id 999 not found for user 1"):
            repo.get_vocabulary_item(999, user_id=1)

    def test_update_vocabulary_item(self, repo, db_session):
        """Test committing and refreshing a vocabulary item."""
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

        # Update the item manually
        vocab.word_phrase = "ett rött äpple"
        vocab.translation = "a red apple"
        vocab.in_learn = False
        updated_vocab = repo.update_vocabulary_item(vocab)

        # Verify the update
        assert updated_vocab.word_phrase == "ett rött äpple"
        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_vocab.in_learn is False
        assert updated_vocab.last_learned is None  # Unchanged

        # Verify in database
        db_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab.id).first()
        assert db_vocab.word_phrase == "ett rött äpple"
        assert db_vocab.translation == "a red apple"
        assert db_vocab.in_learn is False

    def test_update_vocabulary_item_partial(self, repo, db_session):
        """Test committing and refreshing a vocabulary item with partial changes."""
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
        vocab.in_learn = False
        updated_vocab = repo.update_vocabulary_item(vocab)

        # Verify only in_learn changed
        assert updated_vocab.word_phrase == "ett äpple"
        assert updated_vocab.translation == "an apple"
        assert updated_vocab.in_learn is False

    def test_get_vocabulary_item_not_found_existing(self, repo, db_session):
        """Test getting a non-existent vocabulary item."""
        with pytest.raises(ValueError, match="Vocabulary item with id 999 not found for user 1"):
            repo.get_vocabulary_item(999, user_id=1)

    def test_get_vocabulary_item_wrong_user(self, repo, db_session):
        """Test getting a vocabulary item for wrong user."""
        # Add a test item for user 1
        vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
        )
        db_session.add(vocab)
        db_session.commit()

        # Try to get as user 2
        with pytest.raises(ValueError, match="Vocabulary item with id 1 not found for user 2"):
            repo.get_vocabulary_item(vocab.id, user_id=2)

    def test_select_new_daily_word_ids(self, repo, db_session):
        """Test selecting new daily word IDs with cooldown logic (random order)."""

        # Add test vocabulary items
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
            last_learned=datetime.now() - timedelta(days=10),  # Old enough
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            in_learn=True,
            last_learned=datetime.now() - timedelta(days=1),  # Too recent
        )
        vocab4 = VocabularyModel(
            user_id=1,
            word_phrase="en kiwi",
            translation="a kiwi",
            in_learn=False,  # Not in learning
            last_learned=None,
        )
        vocab5 = VocabularyModel(
            user_id=2,
            word_phrase="ett plommon",
            translation="a plum",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3, vocab4, vocab5])
        db_session.commit()

        # Test for user 1 with default cooldown (7 days)
        result = repo.select_new_daily_word_ids(user_id=1)
        result_set = set(result)
        expected_set = {vocab1.id, vocab2.id}

        assert len(result) == 2  # vocab1 and vocab2
        assert result_set == expected_set
        assert vocab3.id not in result_set  # Too recent
        assert vocab4.id not in result_set  # Not in learning
        assert vocab5.id not in result_set  # Wrong user

    def test_select_new_daily_word_ids_custom_cooldown(self, repo, db_session):
        """Test selecting new daily word IDs with custom cooldown period (random order)."""
        from datetime import datetime, timedelta

        # Add test vocabulary items
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=datetime.now() - timedelta(days=3),  # 3 days ago
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            in_learn=True,
            last_learned=datetime.now() - timedelta(days=2),  # 2 days ago
        )

        db_session.add_all([vocab1, vocab2])
        db_session.commit()

        # Test with 5-day cooldown - both should be excluded
        result = repo.select_new_daily_word_ids(user_id=1, cooldown_days=5)
        assert len(result) == 0

        # Test with 1-day cooldown - both should be included
        result = repo.select_new_daily_word_ids(user_id=1, cooldown_days=1)
        result_set = set(result)
        expected_set = {vocab1.id, vocab2.id}

        assert len(result) == 2
        assert result_set == expected_set

    def test_get_vocabulary_item_for_recall(self, repo, db_session):
        """Test getting a vocabulary item for recall (ensures in_learn=True)."""
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
            in_learn=False,  # Not in learning
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

        # Test successful retrieval
        result = repo.get_vocabulary_item_for_recall(vocab1.id, user_id=1)
        assert result.id == vocab1.id
        assert result.word_phrase == "ett äpple"
        assert result.in_learn is True

        # Test item not in learning
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            repo.get_vocabulary_item_for_recall(vocab2.id, user_id=1)

        # Test wrong user
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            repo.get_vocabulary_item_for_recall(vocab3.id, user_id=1)

        # Test non-existent item
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            repo.get_vocabulary_item_for_recall(999, user_id=1)

    def test_get_vocabulary_items_by_ids(self, repo, db_session):
        """Test getting vocabulary items by IDs (ensures in_learn=True)."""
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
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            in_learn=False,  # Not in learning
            last_learned=None,
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3, vocab4])
        db_session.commit()

        # Test successful retrieval
        result = repo.get_vocabulary_items_by_ids([vocab1.id, vocab2.id], user_id=1)
        assert len(result) == 2
        word_phrases = [v.word_phrase for v in result]
        assert "ett äpple" in word_phrases
        assert "en banan" in word_phrases

        # Test with item not in learning (should be excluded)
        result = repo.get_vocabulary_items_by_ids([vocab1.id, vocab3.id], user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "ett äpple"

        # Test with wrong user (should be excluded)
        result = repo.get_vocabulary_items_by_ids([vocab4.id], user_id=1)
        assert len(result) == 0

        # Test empty list
        result = repo.get_vocabulary_items_by_ids([], user_id=1)
        assert len(result) == 0

        # Test non-existent IDs
        result = repo.get_vocabulary_items_by_ids([999, 1000], user_id=1)
        assert len(result) == 0

    def test_update_last_learned(self, repo, db_session):
        """Test updating the last_learned timestamp."""
        from datetime import datetime

        # Add a test item
        vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
        )
        db_session.add(vocab)
        db_session.commit()

        # Record time before update
        before_update = datetime.now()

        # Update last_learned
        updated_vocab = repo.update_last_learned(vocab)

        # Record time after update
        after_update = datetime.now()

        # Verify the update
        assert updated_vocab.last_learned is not None
        assert before_update <= updated_vocab.last_learned <= after_update
        assert updated_vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify in database
        db_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab.id).first()
        assert db_vocab.last_learned is not None
        assert before_update <= db_vocab.last_learned <= after_update

    def test_get_vocabulary_item_by_word_phrase(self, repo, db_session):
        """Test getting a vocabulary item by word phrase."""
        # Add test items
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=2,
            word_phrase="en banan",  # Different word phrase for user 2
            translation="a banana",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2])
        db_session.commit()

        # Test successful retrieval for user 1
        result = repo.get_vocabulary_item_by_word_phrase("ett äpple", user_id=1)
        assert result is not None
        assert result.id == vocab1.id
        assert result.word_phrase == "ett äpple"
        assert result.user_id == 1

        # Test successful retrieval for user 2
        result = repo.get_vocabulary_item_by_word_phrase("en banan", user_id=2)
        assert result is not None
        assert result.id == vocab2.id
        assert result.word_phrase == "en banan"
        assert result.user_id == 2

        # Test non-existent word phrase
        result = repo.get_vocabulary_item_by_word_phrase("nonexistent", user_id=1)
        assert result is None

        # Test wrong user (user 1 looking for user 2's word)
        result = repo.get_vocabulary_item_by_word_phrase("en banan", user_id=1)
        assert result is None

        # Test wrong user (user 2 looking for user 1's word)
        result = repo.get_vocabulary_item_by_word_phrase("ett äpple", user_id=2)
        assert result is None

    def test_delete_vocabulary_item_by_word_phrase(self, repo, db_session):
        """Test deleting (marking as not in learning) a vocabulary item by word phrase."""
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
            in_learn=False,  # Already not in learning
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=2,
            word_phrase="ett päron",  # Different word phrase for user 2
            translation="a pear",
            in_learn=True,
            last_learned=None,
        )

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Test successful deletion
        result = repo.delete_vocabulary_item_by_word_phrase("ett äpple", user_id=1)
        assert result is True

        # Verify item is marked as not in learning
        db_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab1.id).first()
        assert db_vocab.in_learn is False
        assert db_vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify other user's item is unchanged
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2.in_learn is True

        # Test deleting item already not in learning (should still return True but no change)
        result = repo.delete_vocabulary_item_by_word_phrase("en banan", user_id=1)
        assert result is True

        # Test deleting non-existent word phrase
        result = repo.delete_vocabulary_item_by_word_phrase("nonexistent", user_id=1)
        assert result is False

        # Test deleting with wrong user
        result = repo.delete_vocabulary_item_by_word_phrase("ett päron", user_id=1)

    def test_delete_vocabulary_item(self, repo, db_session):
        """Test deleting (marking as not in learning) a vocabulary item by ID."""
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
            in_learn=False,  # Already not in learning
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

        # Test successful deletion
        result = repo.delete_vocabulary_item(vocab1.id, user_id=1)
        assert result is True

        # Verify item is marked as not in learning
        db_vocab = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab1.id).first()
        assert db_vocab.in_learn is False
        assert db_vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify other user's item is unchanged
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2.in_learn is True

        # Test deleting item already not in learning (should still return True)
        result = repo.delete_vocabulary_item(vocab2.id, user_id=1)
        assert result is True

        # Test deleting non-existent item
        result = repo.delete_vocabulary_item(999, user_id=1)
        assert result is False

        # Test deleting with wrong user
        result = repo.delete_vocabulary_item(vocab3.id, user_id=1)
        assert result is False

        # Verify user 2's item is still in learning
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2.in_learn is True
        assert result is False

    def test_hard_delete_vocabulary_item(self, repo, db_session):
        """Test hard deleting a vocabulary item (complete removal from database)."""
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

        # Test successful hard deletion
        result = repo.hard_delete_vocabulary_item(vocab1.id, user_id=1)
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
        result = repo.hard_delete_vocabulary_item(999, user_id=1)
        assert result is False

        # Test deleting with wrong user (should not delete)
        result = repo.hard_delete_vocabulary_item(vocab3.id, user_id=1)
        assert result is False

        # Verify user 2's item still exists
        db_vocab_user2 = db_session.query(VocabularyModel).filter(VocabularyModel.id == vocab3.id).first()
        assert db_vocab_user2 is not None
