"""
Tests for ChatRepository.
"""

from datetime import datetime, timedelta, timezone

import pytest

from runestone.db.chat_repository import ChatRepository
from runestone.db.models import ChatMessage


@pytest.fixture
def chat_repository(db_session):
    """Create a ChatRepository instance."""
    return ChatRepository(db_session)


def test_add_message(chat_repository, db_with_test_user):
    """Test adding a chat message."""
    db, user = db_with_test_user

    chat_repository.add_message(user.id, "user", "Hello Björn")

    messages = chat_repository.get_raw_history(user.id)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Hello Björn"
    assert messages[0].user_id == user.id


def test_get_raw_history_ordering(chat_repository, db_with_test_user):
    """Test that history is returned in chronological order."""
    db, user = db_with_test_user

    chat_repository.add_message(user.id, "user", "Message 1")
    chat_repository.add_message(user.id, "assistant", "Response 1")
    chat_repository.add_message(user.id, "user", "Message 2")

    messages = chat_repository.get_raw_history(user.id)
    assert len(messages) == 3
    assert messages[0].content == "Message 1"
    assert messages[1].content == "Response 1"
    assert messages[2].content == "Message 2"


def test_get_context_for_agent(chat_repository, db_with_test_user, db_session):
    """Test fetching recent context for the agent."""
    db, user = db_with_test_user

    # Add many messages with explicit timestamps
    now = datetime.now(timezone.utc)
    for i in range(15):
        msg = ChatMessage(user_id=user.id, role="user", content=f"Message {i}", created_at=now + timedelta(seconds=i))
        db_session.add(msg)
    db_session.commit()

    context = chat_repository.get_context_for_agent(user.id, limit=10)
    assert len(context) == 10
    # Should be the most recent ones (5 to 14)
    assert context[0].content == "Message 5"
    assert context[9].content == "Message 14"


def test_truncate_history(chat_repository, db_with_test_user, db_session):
    """Test truncating old history."""
    db, user = db_with_test_user

    # Add an old message manually to bypass automatic timestamp
    old_date = datetime.now(timezone.utc) - timedelta(days=10)
    old_msg = ChatMessage(user_id=user.id, role="user", content="Old Message", created_at=old_date)
    db_session.add(old_msg)

    # Add a new message
    chat_repository.add_message(user.id, "user", "New Message")
    db_session.commit()

    # Truncate messages older than 7 days
    chat_repository.truncate_history(user.id, retention_days=7)

    messages = chat_repository.get_raw_history(user.id)
    assert len(messages) == 1
    assert messages[0].content == "New Message"


def test_clear_all_history(chat_repository, db_with_test_user):
    """Test clearing all history for a user."""
    db, user = db_with_test_user

    chat_repository.add_message(user.id, "user", "Msg 1")
    chat_repository.add_message(user.id, "user", "Msg 2")

    chat_repository.clear_all_history(user.id)

    messages = chat_repository.get_raw_history(user.id)
    assert len(messages) == 0
