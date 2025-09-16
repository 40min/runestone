"""
Tests for vocabulary service functionality.

This module contains tests for the vocabulary service.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.api.schemas import Vocabulary as VocabularySchema
from runestone.api.schemas import VocabularyItemCreate
from runestone.db.database import Base
from runestone.db.models import Vocabulary as VocabularyModel
from runestone.services.vocabulary_service import VocabularyService


class TestVocabularyService:
    """Test cases for VocabularyService."""

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
    def service(self, db_session):
        """Create a VocabularyService instance."""
        return VocabularyService(db_session)

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

    def test_get_vocabulary(self, service, db_session):
        """Test retrieving all vocabulary items."""
        # Add some test data
        vocab1 = VocabularyModel(
            user_id=1, word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
        )
        vocab2 = VocabularyModel(user_id=1, word_phrase="en banan", translation="a banana", example_phrase=None)
        vocab3 = VocabularyModel(user_id=2, word_phrase="ett päron", translation="a pear")

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Get all for user 1
        result = service.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 2
        assert isinstance(result[0], VocabularySchema)
        assert result[0].word_phrase == "ett äpple"
        assert result[1].word_phrase == "en banan"

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
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc)
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None,
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc)
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc)
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc)
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
