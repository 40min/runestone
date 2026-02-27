"""
Tests for vocabulary database repository functionality.

This module contains tests for the vocabulary repository.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from runestone.api.schemas import VocabularyItemCreate
from runestone.db.models import User
from runestone.db.models import Vocabulary as VocabularyModel


@pytest.fixture
def basic_vocab_items(vocabulary_model_factory):
    """Create a set of basic vocabulary items for testing."""
    return [
        vocabulary_model_factory(
            word_phrase="ett äpple",
            translation="an apple",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="en banan",
            translation="a banana",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            user_id=2,
            word_phrase="en kiwi",
            translation="a kiwi",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def wildcard_test_items(vocabulary_model_factory):
    """Create vocabulary items for wildcard testing."""
    return [
        vocabulary_model_factory(
            word_phrase="ett äpple",
            translation="an apple",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="en banan",
            translation="a banana",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="ett päron",
            translation="a pear",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="en katt",
            translation="a cat",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def mixed_wildcard_items(vocabulary_model_factory):
    """Create vocabulary items for mixed wildcard testing."""
    return [
        vocabulary_model_factory(
            word_phrase="att lära sig",
            translation="to learn",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="att läsa",
            translation="to read",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="att leka",
            translation="to play",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def special_char_items(vocabulary_model_factory):
    """Create vocabulary items with SQL special characters for testing escaping."""
    return [
        vocabulary_model_factory(
            word_phrase="100% säker",
            translation="100% sure",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="ett_exempel",
            translation="an example",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="back\\slash",
            translation="backslash",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="normal word",
            translation="normal",
            created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def edge_case_items(vocabulary_model_factory):
    """Create vocabulary items for wildcard edge case testing."""
    return [
        vocabulary_model_factory(
            word_phrase="test",
            translation="test",
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="testing",
            translation="testing",
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
        ),
        vocabulary_model_factory(
            word_phrase="t",
            translation="single t",
            created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture(autouse=True)
async def setup_test_users(db_session):
    """Ensure users with IDs 1 and 2 exist for tests that hardcode them."""
    from sqlalchemy import text

    user1 = User(id=1, email="user1@example.com", hashed_password="pw", name="User 1")
    user2 = User(id=2, email="user2@example.com", hashed_password="pw", name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()

    # Reset sequence so automatic ID generation starts after 2
    await db_session.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))"))
    await db_session.commit()

    # Reset session for the actual test
    db_session.expire_all()


@pytest.fixture
def repo(vocabulary_repository):
    """Create a VocabularyRepository instance."""
    return vocabulary_repository


class TestVocabularyRepository:
    """Test cases for VocabularyRepository."""

    async def test_add_vocabulary_items_new(self, repo, db_session):
        """Test adding new vocabulary items."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase=None),
        ]

        await repo.add_vocabulary_items(items, user_id=1)
        await db_session.commit()

        # Verify items were added
        stmt = select(VocabularyModel)
        result = await db_session.execute(stmt)
        vocabularies = result.scalars().all()
        assert len(vocabularies) == 2

        stmt = select(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple")
        result = await db_session.execute(stmt)
        apple_vocab = result.scalars().first()
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.user_id == 1
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None

    async def test_add_vocabulary_items_duplicate(self, repo, db_session):
        """Test that duplicate word_phrases are not added."""
        items = [
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple varje dag."
            ),
            VocabularyItemCreate(
                word_phrase="ett äpple", translation="an apple", example_phrase="Ett äpple är rött."
            ),  # Same word_phrase
        ]

        await repo.add_vocabulary_items(items, user_id=1)
        await db_session.commit()

        # Should only have one entry
        stmt = select(VocabularyModel)
        result = await db_session.execute(stmt)
        vocabularies = result.scalars().all()
        assert len(vocabularies) == 1

        apple_vocab = vocabularies[0]
        assert apple_vocab.word_phrase == "ett äpple"
        assert apple_vocab.translation == "an apple"
        assert apple_vocab.example_phrase == "Jag äter ett äpple varje dag."
        assert apple_vocab.in_learn is True
        assert apple_vocab.last_learned is None

    async def test_upsert_vocabulary_items(self, repo, db_session):
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
        await db_session.commit()

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

        await repo.upsert_vocabulary_items(items, user_id=1)
        await db_session.commit()

        # Expire to ensure we fetch fresh data from DB
        db_session.expire_all()

        # Fetch fresh data
        stmt = select(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple", VocabularyModel.user_id == 1)
        result = await db_session.execute(stmt)
        updated_vocab = result.scalars().first()

        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Ett äpple är rött."
        assert updated_vocab.in_learn is True  # Existing should still be True
        assert updated_vocab.updated_at > initial_updated_at  # Should be updated

        # Verify new item was inserted
        stmt = select(VocabularyModel).filter(VocabularyModel.word_phrase == "en banan", VocabularyModel.user_id == 1)
        result = await db_session.execute(stmt)
        new_vocab = result.scalars().first()

        assert new_vocab.translation == "a banana"
        assert new_vocab.example_phrase is None
        assert new_vocab.in_learn is True
        assert new_vocab.last_learned is None

        # Verify total count
        stmt = select(VocabularyModel).filter(VocabularyModel.user_id == 1)
        result = await db_session.execute(stmt)
        all_vocab = result.scalars().all()
        assert len(all_vocab) == 2

    async def test_get_all_vocabulary(self, repo, db_session):
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
        await db_session.commit()

        # Get all for user 1 (should return most recent first)
        result = await repo.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 2
        # Since we didn't set created_at explicitly, they will be in insertion order
        # But the method should still work
        assert result[0].word_phrase in ["ett äpple", "en banan"]
        assert result[1].word_phrase in ["ett äpple", "en banan"]

        # Get all for user 2
        result = await repo.get_vocabulary(limit=20, user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"

    async def test_get_vocabulary_recent(self, repo, db_session):
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
        await db_session.commit()

        # Get recent for user 1 (should return 3 items, most recent first)
        result = await repo.get_vocabulary(limit=20, user_id=1)
        assert len(result) == 3
        # Should be ordered by created_at descending
        assert result[0].word_phrase == "ett päron"  # Most recent
        assert result[1].word_phrase == "en banan"
        assert result[2].word_phrase == "ett äpple"  # Oldest

        # Test with limit
        result_limited = await repo.get_vocabulary(limit=2, user_id=1)
        assert len(result_limited) == 2
        assert result_limited[0].word_phrase == "ett päron"
        assert result_limited[1].word_phrase == "en banan"

        # Get recent for user 2 (should return 1 item)
        result_user2 = await repo.get_vocabulary(limit=20, user_id=2)
        assert len(result_user2) == 1
        assert result_user2[0].word_phrase == "en kiwi"

    async def test_get_vocabulary_with_search(self, repo, db_session, basic_vocab_items):
        """Test retrieving vocabulary items filtered by search query."""
        # Add test data
        db_session.add_all(basic_vocab_items)
        await db_session.commit()

        # Search for "banan" - should find one match
        result = await repo.get_vocabulary(limit=20, search_query="banan", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search for "ett" - should find two matches (äpple and päron), most recent first
        result = await repo.get_vocabulary(limit=20, search_query="ett", user_id=1)
        assert len(result) == 2
        assert result[0].word_phrase == "ett päron"  # Most recent
        assert result[1].word_phrase == "ett äpple"

        # Search with wildcard "*" - "ban*" should match "banan" (starts with "ban")
        result = await repo.get_vocabulary(limit=20, search_query="*ban*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search case-insensitive - "BANAN" should match "banan"
        result = await repo.get_vocabulary(limit=20, search_query="BANAN", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "en banan"

        # Search for non-existent term
        result = await repo.get_vocabulary(limit=20, search_query="xyz", user_id=1)
        assert len(result) == 0

        # Search for user 2
        result = await repo.get_vocabulary(limit=20, search_query="kiwi", user_id=2)
        assert len(result) == 1
        assert result[0].word_phrase == "en kiwi"

        # Test with limit
        result = await repo.get_vocabulary(limit=1, search_query="ett", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "ett päron"  # Most recent

    async def test_get_vocabulary_with_question_mark_wildcard(self, repo, db_session, wildcard_test_items):
        """Test retrieving vocabulary items with '?' wildcard matching exactly one character."""
        # Add test data with varying patterns
        db_session.add_all(wildcard_test_items)
        await db_session.commit()

        # Search with '?' - "en ?a*" should match "en " + one character + "a" + anything
        # "en ?a*" becomes "en _a%" (no wrapping since wildcards present)
        result = await repo.get_vocabulary(limit=20, search_query="*en ?a*", user_id=1)
        # "*en ?a*" becomes "%en _a%", should match "en banan" (b is one char, then a) and "en katt"
        # (k is one char, then a)
        assert len(result) == 2
        phrases = [r.word_phrase for r in result]
        assert "en banan" in phrases
        assert "en katt" in phrases

        # Search with '?' - "*?tt*" should match words with any single char followed by "tt"
        result = await repo.get_vocabulary(limit=20, search_query="*?tt*", user_id=1)
        # "*?tt*" becomes "%_tt%", should match "ett äpple", "ett päron", "en katt"
        assert len(result) == 3
        phrases = [r.word_phrase for r in result]
        assert "ett äpple" in phrases
        assert "ett päron" in phrases
        assert "en katt" in phrases

        # Search with multiple '?' - "*e?? *" should match any two characters
        result = await repo.get_vocabulary(limit=20, search_query="*e?? *", user_id=1)
        # "*e?? *" becomes "%e__ %", should match "ett äpple" and "ett päron" (ett = e + 2 chars + space)
        assert len(result) == 2
        phrases = [r.word_phrase for r in result]
        assert "ett äpple" in phrases
        assert "ett päron" in phrases

    async def test_get_vocabulary_with_mixed_wildcards(self, repo, db_session, mixed_wildcard_items):
        """Test retrieving vocabulary items with both '*' and '?' wildcards."""
        # Add test data
        db_session.add_all(mixed_wildcard_items)
        await db_session.commit()

        # Search with mixed wildcards - "*att l?*a*" should match "att lära sig", "att läsa", "att leka"
        # Pattern: anything + "att l" + one char + any chars + "a" + anything
        result = await repo.get_vocabulary(limit=20, search_query="*att l?*a*", user_id=1)
        assert len(result) == 3
        phrases = [r.word_phrase for r in result]
        assert "att lära sig" in phrases
        assert "att läsa" in phrases
        assert "att leka" in phrases

        # More specific pattern - "*att l??a*" should match all three (all have exactly 2 chars between
        # l and a in the word containing 'a')
        # "att läsa" - 'lä' before 's' then 'a'
        # "att leka" - 'le' before 'k' then 'a'
        # "att lära sig" - 'lä' before 'r' then 'a'
        result = await repo.get_vocabulary(limit=20, search_query="*att l??a*", user_id=1)
        assert len(result) == 3
        phrases = [r.word_phrase for r in result]
        assert "att läsa" in phrases
        assert "att leka" in phrases
        assert "att lära sig" in phrases

    async def test_get_vocabulary_with_escaped_sql_characters(self, repo, db_session, special_char_items):
        r"""Test that SQL special characters (%, _, \) are properly escaped."""
        # Add test data with special characters
        db_session.add_all(special_char_items)
        await db_session.commit()

        # Search for literal '%' - should match only "100% säker"
        result = await repo.get_vocabulary(limit=20, search_query="*100%*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "100% säker"

        # Search for literal '_' - should match only "ett_exempel"
        result = await repo.get_vocabulary(limit=20, search_query="*ett_exempel*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "ett_exempel"

        # Search for literal '\' - should match only "back\slash"
        result = await repo.get_vocabulary(limit=20, search_query=r"*back\\*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "back\\slash"

        # Verify wildcards still work with escaped chars present
        result = await repo.get_vocabulary(limit=20, search_query="*%*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "100% säker"

    async def test_get_vocabulary_wildcard_edge_cases(self, repo, db_session, edge_case_items):
        """Test edge cases for wildcard patterns."""
        # Add test data
        db_session.add_all(edge_case_items)
        await db_session.commit()

        # Test only wildcards
        result = await repo.get_vocabulary(limit=20, search_query="*", user_id=1)
        assert len(result) == 3  # '*' matches everything

        # '?' alone becomes '_' which matches exactly one character, need * for substring
        result = await repo.get_vocabulary(limit=20, search_query="*?*", user_id=1)
        assert len(result) == 3  # All three items contain at least one character

        # Test empty and None patterns (already covered but verifying)
        result = await repo.get_vocabulary(limit=20, search_query="", user_id=1)
        assert len(result) == 3  # Empty string should match all

        result = await repo.get_vocabulary(limit=20, search_query=None, user_id=1)
        assert len(result) == 3  # None should return all

    async def test_get_vocabulary_with_escaped_wildcards(self, repo, db_session, vocabulary_model_factory):
        """Test that escaped wildcards are treated as literal characters (bug fix test)."""
        # Add test data with literal wildcard characters
        test_items = [
            vocabulary_model_factory(
                word_phrase="file*.txt",
                translation="a file with asterisk",
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="test?.py",
                translation="a file with question mark",
                created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="normal file",
                translation="a normal file",
                created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            ),
        ]
        db_session.add_all(test_items)
        await db_session.commit()

        # Search for literal asterisk using backslash escape: \*
        # This is the key bug case - should find "file*.txt" but not match it as a wildcard
        result = await repo.get_vocabulary(limit=20, search_query=r"\*", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "file*.txt"

        # Search for literal question mark using backslash escape: \?
        result = await repo.get_vocabulary(limit=20, search_query=r"\?", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "test?.py"

        # Verify unescaped wildcards still work as wildcards
        result = await repo.get_vocabulary(limit=20, search_query="*file*", user_id=1)
        # "*file*" as a wildcard should match both "file*.txt" and "normal file" (both contain "file")
        assert len(result) == 2
        phrases = [r.word_phrase for r in result]
        assert "file*.txt" in phrases
        assert "normal file" in phrases

    async def test_get_vocabulary_with_escaped_wildcards_in_pattern(self, repo, db_session, vocabulary_model_factory):
        """Test complex patterns with both escaped and unescaped wildcards."""
        # Add test data
        test_items = [
            vocabulary_model_factory(
                word_phrase="log_2024*.txt",
                translation="log file with wildcard",
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="log_2024_jan.txt",
                translation="january log",
                created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="log-2024.txt",
                translation="dash log",
                created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            ),
        ]
        db_session.add_all(test_items)
        await db_session.commit()

        # Search for pattern with escaped wildcard and SQL underscore
        # "*log_2024\**" should match only "log_2024*.txt" (literal asterisk)
        result = await repo.get_vocabulary(limit=20, search_query=r"*log_2024\**", user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "log_2024*.txt"

        # Search with unescaped wildcard should match multiple
        # "*log*2024*" should match all three (wildcard before and after 2024)
        result = await repo.get_vocabulary(limit=20, search_query="*log*2024*", user_id=1)
        assert len(result) == 3

    async def test_get_vocabulary_item(self, repo, db_session):
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
        await db_session.commit()

        # Get the item
        retrieved_vocab = await repo.get_vocabulary_item(vocab.id, user_id=1)

        # Verify
        assert retrieved_vocab.id == vocab.id
        assert retrieved_vocab.word_phrase == "ett äpple"
        assert retrieved_vocab.translation == "an apple"

    async def test_get_vocabulary_item_not_found(self, repo, db_session):
        """Test getting a non-existent vocabulary item."""
        with pytest.raises(ValueError, match="Vocabulary item with id 999 not found for user 1"):
            await repo.get_vocabulary_item(999, user_id=1)

    async def test_update_vocabulary_item(self, repo, db_session):
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
        await db_session.commit()

        # Update the item manually
        vocab.word_phrase = "ett rött äpple"
        vocab.translation = "a red apple"
        vocab.in_learn = False
        updated_vocab = await repo.update_vocabulary_item(vocab)

        # Verify the update
        assert updated_vocab.word_phrase == "ett rött äpple"
        assert updated_vocab.translation == "a red apple"
        assert updated_vocab.example_phrase == "Jag äter ett äpple varje dag."  # Unchanged
        assert updated_vocab.in_learn is False
        assert updated_vocab.last_learned is None  # Unchanged

        # Verify in database
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab.word_phrase == "ett rött äpple"
        assert db_vocab.translation == "a red apple"
        assert db_vocab.in_learn is False

    async def test_update_vocabulary_item_partial(self, repo, db_session):
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
        await db_session.commit()

        # Update only one field
        vocab.in_learn = False
        updated_vocab = await repo.update_vocabulary_item(vocab)

        # Verify only in_learn changed
        assert updated_vocab.word_phrase == "ett äpple"
        assert updated_vocab.translation == "an apple"
        assert updated_vocab.in_learn is False

    async def test_get_vocabulary_item_not_found_existing(self, repo, db_session):
        """Test getting a non-existent vocabulary item."""
        with pytest.raises(ValueError, match="Vocabulary item with id 999 not found for user 1"):
            await repo.get_vocabulary_item(999, user_id=1)

    async def test_get_vocabulary_item_wrong_user(self, repo, db_session):
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
        await db_session.commit()

        # Try to get as user 2
        with pytest.raises(ValueError, match="Vocabulary item with id 1 not found for user 2"):
            await repo.get_vocabulary_item(vocab.id, user_id=2)

    async def test_select_new_daily_words(self, repo, db_session):
        """Test selecting new daily words with cooldown logic (random order)."""

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
        await db_session.commit()

        # Test for user 1 with default cooldown (7 days)
        result = await repo.select_new_daily_words(user_id=1)
        result_ids = [word.id for word in result]
        result_set = set(result_ids)
        expected_set = {vocab1.id, vocab2.id}

        assert len(result) == 2  # vocab1 and vocab2
        assert result_set == expected_set
        assert vocab3.id not in result_set  # Too recent
        assert vocab4.id not in result_set  # Not in learning
        assert vocab5.id not in result_set  # Wrong user

    async def test_select_new_daily_words_custom_cooldown(self, repo, db_session):
        """Test selecting new daily words with custom cooldown period (random order)."""
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
        await db_session.commit()

        # Test with 5-day cooldown - both should be excluded
        result = await repo.select_new_daily_words(user_id=1, cooldown_days=5)
        assert len(result) == 0

        # Test with 1-day cooldown - both should be included
        result = await repo.select_new_daily_words(user_id=1, cooldown_days=1)
        result_ids = [word.id for word in result]
        result_set = set(result_ids)
        expected_set = {vocab1.id, vocab2.id}

        assert len(result) == 2
        assert result_set == expected_set

    async def test_select_new_daily_words_prioritization(self, repo, db_session):
        """Test that prioritized words are selected first in daily selection."""
        # Add test items: 3 priority words, 3 regular words
        priority_items = [
            VocabularyModel(user_id=1, word_phrase=f"priority_{i}", translation="...", priority_learn=True)
            for i in range(3)
        ]
        regular_items = [
            VocabularyModel(user_id=1, word_phrase=f"regular_{i}", translation="...", priority_learn=False)
            for i in range(3)
        ]

        db_session.add_all(priority_items + regular_items)
        await db_session.commit()

        # Select with limit=4. Should get all 3 priority items + 1 regular item.
        result = await repo.select_new_daily_words(user_id=1, limit=4)

        assert len(result) == 4
        # First 3 should be priority items
        priority_word_phrases = {item.word_phrase for item in priority_items}
        for i in range(3):
            assert result[i].word_phrase in priority_word_phrases
            assert result[i].priority_learn is True

        # Last one should be a regular item
        regular_word_phrases = {item.word_phrase for item in regular_items}
        assert result[3].word_phrase in regular_word_phrases
        assert result[3].priority_learn is False

    async def test_get_vocabulary_item_for_recall(self, repo, db_session):
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
        await db_session.commit()

        # Test successful retrieval
        result = await repo.get_vocabulary_item_for_recall(vocab1.id, user_id=1)
        assert result.id == vocab1.id
        assert result.word_phrase == "ett äpple"
        assert result.in_learn is True

        # Test item not in learning
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            await repo.get_vocabulary_item_for_recall(vocab2.id, user_id=1)

        # Test wrong user
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            await repo.get_vocabulary_item_for_recall(vocab3.id, user_id=1)

        # Test non-existent item
        with pytest.raises(ValueError, match="not found for user 1 or not in learning"):
            await repo.get_vocabulary_item_for_recall(999, user_id=1)

    async def test_get_vocabulary_items_by_ids(self, repo, db_session):
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
        await db_session.commit()

        # Test successful retrieval
        result = await repo.get_vocabulary_items_by_ids([vocab1.id, vocab2.id], user_id=1)
        assert len(result) == 2
        word_phrases = [v.word_phrase for v in result]
        assert "ett äpple" in word_phrases
        assert "en banan" in word_phrases

        # Test with item not in learning (should be excluded)
        result = await repo.get_vocabulary_items_by_ids([vocab1.id, vocab3.id], user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "ett äpple"

        # Test with wrong user (should be excluded)
        result = await repo.get_vocabulary_items_by_ids([vocab4.id], user_id=1)
        assert len(result) == 0

        # Test empty list
        result = await repo.get_vocabulary_items_by_ids([], user_id=1)
        assert len(result) == 0

        # Test non-existent IDs
        result = await repo.get_vocabulary_items_by_ids([999, 1000], user_id=1)
        assert len(result) == 0

    async def test_update_last_learned(self, repo, db_session):
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
        await db_session.commit()

        # Record time before update
        before_update = datetime.now(timezone.utc)

        # Update last_learned
        await repo.update_last_learned(vocab)
        await db_session.refresh(vocab)

        # Verify it was updated
        assert vocab.last_learned is not None
        assert before_update <= vocab.last_learned <= datetime.now(timezone.utc)
        assert vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify in database
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab.last_learned is not None
        assert before_update <= db_vocab.last_learned <= datetime.now(timezone.utc)

    async def test_get_vocabulary_item_by_word_phrase(self, repo, db_session):
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
        await db_session.commit()

        # Test successful retrieval for user 1
        result = await repo.get_vocabulary_item_by_word_phrase("ett äpple", user_id=1)
        assert result is not None
        assert result.id == vocab1.id
        assert result.word_phrase == "ett äpple"
        assert result.user_id == 1

        # Test successful retrieval for user 2
        result = await repo.get_vocabulary_item_by_word_phrase("en banan", user_id=2)
        assert result is not None
        assert result.id == vocab2.id
        assert result.word_phrase == "en banan"
        assert result.user_id == 2

        # Test non-existent word phrase
        result = await repo.get_vocabulary_item_by_word_phrase("nonexistent", user_id=1)
        assert result is None

        # Test wrong user (user 1 looking for user 2's word)
        result = await repo.get_vocabulary_item_by_word_phrase("en banan", user_id=1)
        assert result is None

        # Test wrong user (user 2 looking for user 1's word)
        result = await repo.get_vocabulary_item_by_word_phrase("ett äpple", user_id=2)
        assert result is None

    async def test_delete_vocabulary_item_by_word_phrase(self, repo, db_session):
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
        await db_session.commit()

        # Test successful deletion
        result = await repo.delete_vocabulary_item_by_word_phrase("ett äpple", user_id=1)
        assert result is True

        # Verify item is marked as not in learning
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab1.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab.in_learn is False
        assert db_vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify other user's item is unchanged
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab3.id)
        result = await db_session.execute(stmt)
        db_vocab_user2 = result.scalars().first()
        assert db_vocab_user2.in_learn is True

        # Test deleting item already not in learning (should still return True but no change)
        result = await repo.delete_vocabulary_item_by_word_phrase("en banan", user_id=1)
        assert result is True

        # Test deleting non-existent word phrase
        result = await repo.delete_vocabulary_item_by_word_phrase("nonexistent", user_id=1)
        assert result is False

        # Test deleting with wrong user
        result = await repo.delete_vocabulary_item_by_word_phrase("ett päron", user_id=1)
        assert result is False

    async def test_delete_vocabulary_item(self, repo, db_session):
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
        await db_session.commit()

        # Test successful deletion
        result = await repo.delete_vocabulary_item(vocab1.id, user_id=1)
        assert result is True

        # Verify item is marked as not in learning
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab1.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab.in_learn is False
        assert db_vocab.word_phrase == "ett äpple"  # Other fields unchanged

        # Verify other user's item is unchanged
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab3.id)
        result = await db_session.execute(stmt)
        db_vocab_user2 = result.scalars().first()
        assert db_vocab_user2.in_learn is True

        # Test deleting item already not in learning (should still return True)
        result = await repo.delete_vocabulary_item(vocab2.id, user_id=1)
        assert result is True

        # Test deleting non-existent item
        result = await repo.delete_vocabulary_item(999, user_id=1)
        assert result is False

        # Test deleting with wrong user
        result = await repo.delete_vocabulary_item(vocab3.id, user_id=1)

        # Verify user 2's item is still in learning
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab3.id)
        result = await db_session.execute(stmt)
        db_vocab_user2 = result.scalars().first()
        assert db_vocab_user2.in_learn is True

    async def test_hard_delete_vocabulary_item(self, repo, db_session):
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
        await db_session.commit()

        # Verify initial count
        stmt = select(func.count()).select_from(VocabularyModel)
        result = await db_session.execute(stmt)
        initial_count = result.scalar()
        assert initial_count == 3

        # Test successful hard deletion
        result = await repo.hard_delete_vocabulary_item(vocab1.id, user_id=1)
        assert result is True

        # Verify item is completely removed from database
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab1.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab is None

        # Verify other items still exist
        stmt = select(func.count()).select_from(VocabularyModel)
        result = await db_session.execute(stmt)
        remaining_count = result.scalar()
        assert remaining_count == 2

        # Verify other user's item is unchanged
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab3.id)
        result = await db_session.execute(stmt)
        db_vocab_user2 = result.scalars().first()
        assert db_vocab_user2 is not None
        assert db_vocab_user2.in_learn is True

        # Test deleting non-existent item
        result = await repo.hard_delete_vocabulary_item(999, user_id=1)
        assert result is False

        # Test deleting with wrong user (should not delete)
        result = await repo.hard_delete_vocabulary_item(vocab3.id, user_id=1)
        assert result is False

        # Verify user 2's item still exists
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab3.id)
        result = await db_session.execute(stmt)
        db_vocab_user2 = result.scalars().first()
        assert db_vocab_user2 is not None

    async def test_update_last_learned_increments_learned_times(self, repo, db_session):
        """Test that update_last_learned increments the learned_times counter."""

        # Add a test item with initial learned_times = 0
        vocab = VocabularyModel(
            user_id=1,
            word_phrase="ett äpple",
            translation="an apple",
            in_learn=True,
            last_learned=None,
            learned_times=0,
        )
        db_session.add(vocab)
        await db_session.commit()

        # Record time before update
        before_update = datetime.now(timezone.utc)

        # Update last_learned (should increment learned_times)
        await repo.update_last_learned(vocab)
        await db_session.refresh(vocab)

        # Record time after update
        after_update = datetime.now(timezone.utc)

        # Verify the update
        assert vocab.last_learned is not None
        assert before_update <= vocab.last_learned <= after_update
        assert vocab.learned_times == 1  # Should be incremented from 0 to 1

        # Verify in database
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab.id)
        result = await db_session.execute(stmt)
        db_vocab = result.scalars().first()
        assert db_vocab.last_learned is not None
        assert before_update <= db_vocab.last_learned <= after_update
        assert db_vocab.learned_times == 1

        # Test multiple increments
        await repo.update_last_learned(vocab)
        await db_session.refresh(vocab)
        assert vocab.learned_times == 2  # Should increment to 2

        # Verify in database
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab.id)
        result = await db_session.execute(stmt)
        db_vocab2 = result.scalars().first()
        assert db_vocab2.learned_times == 2

    async def test_select_new_daily_words_with_exclusions(self, repo, db_session):
        """Test that select_new_daily_words properly excludes specified word IDs."""
        # Create test vocabulary items (similar to service test fixture)
        vocab1 = VocabularyModel(
            user_id=1,
            word_phrase="hello",
            translation="hej",
            example_phrase="Hello, how are you?",
            in_learn=True,
            last_learned=None,
        )
        vocab2 = VocabularyModel(
            user_id=1,
            word_phrase="goodbye",
            translation="hej då",
            example_phrase="Goodbye, see you later!",
            in_learn=True,
            last_learned=None,
        )
        vocab3 = VocabularyModel(
            user_id=1,
            word_phrase="thank you",
            translation="tack",
            example_phrase="Thank you for your help.",
            in_learn=True,
            last_learned=None,
        )
        vocab4 = VocabularyModel(
            user_id=2,
            word_phrase="water",
            translation="vatten",
            example_phrase="I need water.",
            in_learn=True,
            last_learned=None,
        )
        db_session.add_all([vocab1, vocab2, vocab3, vocab4])
        await db_session.commit()

        # Ensure all words are available (no cooldown)
        stmt = select(VocabularyModel).filter(VocabularyModel.user_id == 1)
        result = await db_session.execute(stmt)
        words = result.scalars().all()
        for word in words:
            word.last_learned = datetime.now() - timedelta(days=10)
        await db_session.commit()

        # Select words excluding specific IDs
        excluded_ids = [vocab1.id]  # Exclude "hello" (id=vocab1.id)
        selected_words = await repo.select_new_daily_words(
            user_id=1, cooldown_days=7, limit=5, excluded_word_ids=excluded_ids
        )

        # Verify excluded word is not in results
        selected_ids = [w.id for w in selected_words]
        assert vocab1.id not in selected_ids
        assert len(selected_words) == 2  # Should get goodbye and thank you

    async def test_update_last_learned_increments_learned_times_none(self, repo, db_session):
        """Test that update_last_learned handles None learned_times gracefully."""
        vocab_with_none = VocabularyModel(
            user_id=1,
            word_phrase="en banan",
            translation="a banana",
            in_learn=True,
            last_learned=None,
            learned_times=None,  # Test None value
        )
        db_session.add(vocab_with_none)
        await db_session.commit()

        await repo.update_last_learned(vocab_with_none)
        await db_session.refresh(vocab_with_none)
        assert vocab_with_none.learned_times == 1
        stmt = select(VocabularyModel).filter(VocabularyModel.id == vocab_with_none.id)
        result = await db_session.execute(stmt)
        db_vocab_none = result.scalars().first()
        assert db_vocab_none.learned_times == 1

    async def test_get_vocabulary_with_precise_search(self, repo, db_session, vocabulary_model_factory):
        """Test precise search functionality (exact case-insensitive match)."""
        # Add test data with case variations
        test_items = [
            vocabulary_model_factory(
                word_phrase="apple",
                translation="äpple",
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="APPLE",
                translation="ÄPPLE",
                created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="pineapple",
                translation="ananas",
                created_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            ),
            vocabulary_model_factory(
                word_phrase="app",
                translation="app",
                created_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
            ),
        ]
        db_session.add_all(test_items)
        await db_session.commit()

        # Test precise search for "apple" - should match only exact case-insensitive matches
        result = await repo.get_vocabulary(limit=20, search_query="apple", precise=True, user_id=1)
        assert len(result) == 2  # "apple" and "APPLE"
        phrases = [r.word_phrase for r in result]
        assert "apple" in phrases
        assert "APPLE" in phrases
        assert "pineapple" not in phrases  # No partial match
        assert "app" not in phrases  # No partial match

        # Test case-insensitive precise search
        result = await repo.get_vocabulary(limit=20, search_query="APPLE", precise=True, user_id=1)
        assert len(result) == 2  # Same two items
        phrases = [r.word_phrase for r in result]
        assert "apple" in phrases
        assert "APPLE" in phrases

        # Test precise search for "pineapple" - should match only exact
        result = await repo.get_vocabulary(limit=20, search_query="pineapple", precise=True, user_id=1)
        assert len(result) == 1
        assert result[0].word_phrase == "pineapple"

        # Test precise search for non-existent term
        result = await repo.get_vocabulary(limit=20, search_query="banana", precise=True, user_id=1)
        assert len(result) == 0

        # Test precise search with None query (should return all)
        result = await repo.get_vocabulary(limit=20, search_query=None, precise=True, user_id=1)
        assert len(result) == 4

        # Test precise search with empty string (should return all)
        result = await repo.get_vocabulary(limit=20, search_query="", precise=True, user_id=1)
        assert len(result) == 4

    async def test_get_vocabulary_precise_vs_partial_comparison(self, repo, db_session, vocabulary_model_factory):
        """Test that precise and partial search produce different results."""
        # Add test data
        test_items = [
            vocabulary_model_factory(
                word_phrase="test", translation="test", created_at=datetime(2023, 1, 1, tzinfo=timezone.utc)
            ),
            vocabulary_model_factory(
                word_phrase="testing", translation="testing", created_at=datetime(2023, 1, 2, tzinfo=timezone.utc)
            ),
            vocabulary_model_factory(
                word_phrase="contest", translation="contest", created_at=datetime(2023, 1, 3, tzinfo=timezone.utc)
            ),
        ]
        db_session.add_all(test_items)
        await db_session.commit()

        # Partial search for "test" - should match all three (substring match)
        partial_result = await repo.get_vocabulary(limit=20, search_query="test", precise=False, user_id=1)
        assert len(partial_result) == 3
        partial_phrases = [r.word_phrase for r in partial_result]
        assert "test" in partial_phrases
        assert "testing" in partial_phrases
        assert "contest" in partial_phrases

        # Precise search for "test" - should match only exact
        precise_result = await repo.get_vocabulary(limit=20, search_query="test", precise=True, user_id=1)
        assert len(precise_result) == 1
        assert precise_result[0].word_phrase == "test"


class TestVocabularyRepositoryStats:
    """Test cases for vocabulary repository statistics methods."""

    async def test_get_words_in_learn_count(self, repo, db_session):
        """Test counting words in learning (in_learn=True AND last_learned IS NOT NULL)."""

        # Create test user
        user = User(
            email="stats@example.com",
            hashed_password="dummy",
            name="Stats User",
        )
        db_session.add(user)
        await db_session.commit()

        # Add vocabulary items
        vocab_items = [
            VocabularyModel(
                user_id=user.id,
                word_phrase="word1",
                translation="trans1",
                in_learn=True,
                last_learned=datetime.now(timezone.utc),  # Has last_learned
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word2",
                translation="trans2",
                in_learn=True,
                last_learned=datetime.now(timezone.utc),  # Has last_learned
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word3",
                translation="trans3",
                in_learn=False,  # Not in learning
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word4",
                translation="trans4",
                in_learn=True,
                last_learned=None,  # No last_learned, shouldn't be counted
            ),
        ]
        db_session.add_all(vocab_items)
        await db_session.commit()

        # Test stats - only word1 and word2 should be counted (in_learn=True AND last_learned IS NOT NULL)
        count = await repo.get_words_in_learn_count(user.id)
        assert count == 2

    async def test_get_words_skipped_count(self, repo, db_session):
        """Test counting skipped words (in_learn=False)."""

        # Create test user
        user = User(
            email="skipped@example.com",
            hashed_password="dummy",
            name="Skipped User",
        )
        db_session.add(user)
        await db_session.commit()

        # Add vocabulary items
        vocab_items = [
            VocabularyModel(
                user_id=user.id,
                word_phrase="word1",
                translation="trans1",
                in_learn=True,
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word2",
                translation="trans2",
                in_learn=False,  # Skipped
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word3",
                translation="trans3",
                in_learn=False,  # Skipped
            ),
        ]
        db_session.add_all(vocab_items)
        await db_session.commit()

        # Test stats - word2 and word3 should be counted (in_learn=False)
        count = await repo.get_words_skipped_count(user.id)
        assert count == 2

    async def test_get_overall_words_count(self, repo, db_session):
        """Test counting all words for a user."""

        # Create test user
        user = User(
            email="overall@example.com",
            hashed_password="dummy",
            name="Overall User",
        )
        db_session.add(user)
        await db_session.commit()

        # Add vocabulary items
        vocab_items = [
            VocabularyModel(
                user_id=user.id,
                word_phrase="word1",
                translation="trans1",
                in_learn=True,
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word2",
                translation="trans2",
                in_learn=True,
            ),
            VocabularyModel(
                user_id=user.id,
                word_phrase="word3",
                translation="trans3",
                in_learn=False,
            ),
        ]
        db_session.add_all(vocab_items)
        await db_session.commit()

        # Test stats - all 3 words should be counted
        count = await repo.get_overall_words_count(user.id)
        assert count == 3
