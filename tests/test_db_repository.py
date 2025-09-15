"""
Tests for vocabulary database repository functionality.

This module contains tests for the vocabulary repository.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.db.database import Base
from runestone.db.models import Vocabulary as VocabularyModel
from runestone.db.repository import VocabularyRepository
from runestone.api.schemas import VocabularyItemCreate


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
                word_phrase="ett äpple",
                translation="an apple",
                example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(
                word_phrase="en banan",
                translation="a banana",
                example_phrase=None
            )
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

    def test_add_vocabulary_items_duplicate(self, repo, db_session):
        """Test that duplicate word_phrases are not added."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple",
                translation="an apple",
                example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(
                word_phrase="ett äpple",
                translation="an apple",
                example_phrase="Ett äpple är rött."
            )  # Same word_phrase
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

    def test_get_all_vocabulary(self, repo, db_session):
        """Test retrieving all vocabulary items."""
        # Add some test data
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            example_phrase="Jag äter ett äpple varje dag."
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            example_phrase=None
        )
        vocab3 = VocabularyModel(
            user_id=2,
            word_phrase="ett päron",
            translation="a pear"
        )

        db_session.add_all([vocab1, vocab2, vocab3])
        db_session.commit()

        # Get all for user 1
        result = repo.get_all_vocabulary(user_id=1)
        assert len(result) == 2
        assert result[0].word_phrase == "ett äpple"
        assert result[1].word_phrase == "en banan"

        # Get all for user 2
        result = repo.get_all_vocabulary(user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"