"""
Tests for ChatService.
"""

from unittest.mock import Mock

import pytest

from runestone.db.chat_repository import ChatRepository
from runestone.services.chat_service import ChatService


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentService."""
    mock = Mock()
    mock.generate_response.return_value = "Björn's reply"
    return mock


@pytest.fixture
def chat_service(db_session, mock_agent_service):
    """Create a ChatService instance with real repository and mock agent."""
    repository = ChatRepository(db_session)
    mock_settings = Mock()
    mock_settings.chat_history_retention_days = 7
    return ChatService(mock_settings, repository, mock_agent_service)


@pytest.mark.anyio
async def test_process_message_orchestration(chat_service, db_with_test_user, mock_agent_service):
    """Test the full flow of processing a message."""
    db, user = db_with_test_user

    response = await chat_service.process_message(user.id, "Hej Björn")

    assert response == "Björn's reply"

    # Verify persistence
    history = chat_service.get_history(user.id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hej Björn"
    assert history[1].role == "assistant"
    assert history[1].content == "Björn's reply"

    # Verify agent was called with correct context
    # Since it's the first message, context should be empty (or contain just the new message
    # if we didn't slice correctly)
    # Actually, in process_message:
    # assistant_text = self.agent_service.generate_response(message_text, context_schemas[:-1])
    # context_schemas includes the message we JUST saved. So [:-1] should be empty for first message.
    mock_agent_service.generate_response.assert_called_once()
    args, kwargs = mock_agent_service.generate_response.call_args
    assert args[0] == "Hej Björn"
    assert args[1] == []  # Context should be empty for first message


@pytest.mark.anyio
async def test_process_message_with_history(chat_service, db_with_test_user, mock_agent_service):
    """Test process_message when there is existing history."""
    db, user = db_with_test_user

    # Add some history
    await chat_service.process_message(user.id, "Message 1")
    mock_agent_service.generate_response.reset_mock()

    # Process second message
    await chat_service.process_message(user.id, "Message 2")

    mock_agent_service.generate_response.assert_called_once()
    args, kwargs = mock_agent_service.generate_response.call_args
    assert args[0] == "Message 2"
    # Context should contain Message 1 (user) and Response 1 (assistant)
    context = args[1]
    assert len(context) == 2
    assert context[0].content == "Message 1"
    assert context[1].content == "Björn's reply"


def test_clear_history(chat_service, db_with_test_user):
    """Test clearing history via service."""
    db, user = db_with_test_user
    chat_service.repository.add_message(user.id, "user", "Test")

    chat_service.clear_history(user.id)
    assert len(chat_service.get_history(user.id)) == 0
