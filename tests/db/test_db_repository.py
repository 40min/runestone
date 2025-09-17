"""
Tests for vocabulary database repository functionality.

This module contains tests for the vocabulary repository.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.api.schemas import VocabularyItemCreate
from runestone.db.database import Base
from runestone.db.models import Vocabulary as VocabularyModel
from runestone.db.repository import VocabularyRepository


class TestVocabularyRepository:
    """Test cases for VocabularyRepository."""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def repo(self, db_session):
        """Create a VocabularyRepository instance."""
        return VocabularyRepository(db_session)

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
        assert apple_vocab.showed_times == 0

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
        assert apple_vocab.showed_times == 0

    def test_get_all_vocabulary(self, repo, db_session):
        """Test retrieving all vocabulary items."""
        # Add some test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag.",
            in_learn=True,
            showed_times=0,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            in_learn=True,
            showed_times=0,
        )
        vocab3 = VocabularyModel(
            user_id=2, word_phrase="ett päron", translation="a pear", in_learn=True, showed_times=0
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
            showed_times=0,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
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
            showed_times=0,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
            in_learn=True,
            showed_times=0,
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
            showed_times=0,
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
            showed_times=0,
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
        assert updated_vocab.showed_times == 0  # Unchanged

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
            showed_times=0,
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
            showed_times=0,
        )
        db_session.add(vocab)
        db_session.commit()

        # Try to get as user 2
        with pytest.raises(ValueError, match="Vocabulary item with id 1 not found for user 2"):
            repo.get_vocabulary_item(vocab.id, user_id=2)
