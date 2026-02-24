"""
Tests for ChatService.
"""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from runestone.db.chat_repository import ChatRepository
from runestone.services.chat_service import ChatService


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentService."""
    mock = AsyncMock()
    mock.generate_response.return_value = ("Björn's reply", None)
    return mock


@pytest.fixture
def mock_vocabulary_service():
    """Create a mock VocabularyService."""
    return Mock()


@pytest.fixture
def mock_tts_service():
    """Create a mock TTSService."""
    return Mock()


@pytest.fixture
def mock_user_service():
    """Create a mock UserService."""
    mock = Mock()
    # Setup default mock behavior
    mock_user = Mock()
    mock_user.id = 1
    mock_user.current_chat_id = str(uuid4())
    mock.get_user_by_id.return_value = mock_user
    mock.get_or_create_current_chat_id.return_value = mock_user.current_chat_id
    mock.rotate_current_chat_id.return_value = str(uuid4())

    mock_profile = Mock()
    mock_profile.personal_info = None
    mock_profile.areas_to_improve = None
    mock_profile.knowledge_strengths = None
    mock.get_user_profile.return_value = mock_profile
    return mock


@pytest.fixture
def mock_memory_item_service():
    """Create a mock MemoryItemService."""
    return Mock()


@pytest.fixture
def mock_processor():
    """Create a mock RunestoneProcessor."""
    mock = Mock()
    # Default behavior for successful OCR
    mock_ocr_result = Mock()
    mock_ocr_result.transcribed_text = "Hej världen"
    mock.run_ocr.return_value = mock_ocr_result
    return mock


@pytest.fixture
def chat_service(
    db_session,
    mock_agent_service,
    mock_user_service,
    mock_processor,
    mock_vocabulary_service,
    mock_tts_service,
    mock_memory_item_service,
):
    """Create a ChatService instance with real repository and mock agent/user services."""
    repository = ChatRepository(db_session)
    mock_settings = Mock()
    mock_settings.chat_history_retention_days = 7
    return ChatService(
        mock_settings,
        repository,
        mock_user_service,
        mock_agent_service,
        mock_processor,
        mock_vocabulary_service,
        mock_tts_service,
        mock_memory_item_service,
    )


@pytest.mark.anyio
async def test_process_message_orchestration(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test the full flow of processing a message."""
    db, user = db_with_test_user

    # Configure mock user service to return the DB user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    response, sources = await chat_service.process_message(user.id, "Hej Björn")

    assert response == "Björn's reply"
    assert sources is None

    # Verify persistence
    history = chat_service.get_history(user.id, user.current_chat_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hej Björn"
    assert history[1].role == "assistant"
    assert history[1].content == "Björn's reply"

    # Verify agent was called with correct context
    mock_agent_service.generate_response.assert_called_once()
    kwargs = mock_agent_service.generate_response.call_args.kwargs

    assert kwargs["message"] == "Hej Björn"
    assert kwargs["history"] == []
    assert kwargs["user"] == user


@pytest.mark.anyio
async def test_process_message_with_history(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test process_message when there is existing history."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    # Add some history
    await chat_service.process_message(user.id, "Message 1")
    mock_agent_service.generate_response.reset_mock()

    # Process second message
    await chat_service.process_message(user.id, "Message 2")

    mock_agent_service.generate_response.assert_called_once()
    kwargs = mock_agent_service.generate_response.call_args.kwargs

    assert kwargs["message"] == "Message 2"
    # Context should contain Message 1 (user) and Response 1 (assistant)
    history = kwargs["history"]
    assert len(history) == 2
    assert history[0].content == "Message 1"
    assert history[1].content == "Björn's reply"


@pytest.mark.anyio
async def test_process_image_message_success(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, mock_processor
):
    """Test successful image processing."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    # Configure processor mock for this test
    ocr_result = Mock()
    ocr_result.transcribed_text = "Hej. Hur mår du?"
    mock_processor.run_ocr.return_value = ocr_result

    # Process image
    response = await chat_service.process_image_message(user.id, b"fake_image_bytes")

    assert response == "Björn's reply"

    # Verify processor called
    mock_processor.run_ocr.assert_called_once_with(b"fake_image_bytes")

    # Verify agent call includes OCR text in prompt
    mock_agent_service.generate_response.assert_called_once()
    kwargs = mock_agent_service.generate_response.call_args.kwargs
    assert "Hej. Hur mår du?" in kwargs["message"]

    # Verify history persistence (only assistant message for images)
    history = chat_service.get_history(user.id, user.current_chat_id)
    assert len(history) == 1
    assert history[0].role == "assistant"
    assert history[0].content == "Björn's reply"


@pytest.mark.anyio
async def test_process_image_message_ocr_failure(chat_service, db_with_test_user, mock_processor):
    """Test handling of empty OCR results."""
    db, user = db_with_test_user
    from runestone.core.exceptions import RunestoneError

    # Configure processor to return empty text
    ocr_result = Mock()
    ocr_result.transcribed_text = ""
    mock_processor.run_ocr.return_value = ocr_result

    with pytest.raises(RunestoneError, match="Could not recognize text"):
        await chat_service.process_image_message(user.id, b"fake_image_bytes")


@pytest.mark.anyio
async def test_process_image_message_uses_mother_tongue(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, mock_processor
):
    """Test that translation prompt uses user's mother tongue."""
    db, user = db_with_test_user

    # Set user's mother tongue
    user.mother_tongue = "Spanish"
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    # Configure processor mock
    ocr_result = Mock()
    ocr_result.transcribed_text = "Hej världen"
    mock_processor.run_ocr.return_value = ocr_result

    # Process image
    await chat_service.process_image_message(user.id, b"fake_image_bytes")

    # Verify agent was called with mother tongue in prompt
    mock_agent_service.generate_response.assert_called_once()
    kwargs = mock_agent_service.generate_response.call_args.kwargs
    prompt = kwargs["message"]

    # Verify Spanish is mentioned in the prompt
    assert "Spanish" in prompt
    assert "Hej världen" in prompt


def test_clear_history(chat_service, db_with_test_user):
    """Test clearing history via service."""
    db, user = db_with_test_user
    chat_id = str(uuid4())
    chat_service.repository.add_message(user.id, chat_id, "user", "Test")
    chat_service.user_service.rotate_current_chat_id.return_value = str(uuid4())
    chat_service.clear_history(user.id)
    chat_service.user_service.rotate_current_chat_id.assert_called_once_with(user.id)


@pytest.mark.anyio
async def test_process_message_persists_sources(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test that sources are stored and returned in history."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id
    mock_agent_service.generate_response.return_value = (
        "Svar med källor",
        [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}],
    )

    await chat_service.process_message(user.id, "Nyheter tack")

    history = chat_service.get_history(user.id, user.current_chat_id)
    assistant_messages = [msg for msg in history if msg.role == "assistant"]
    assert len(assistant_messages) == 1
    assert [source.model_dump(mode="json") for source in assistant_messages[0].sources] == [
        {"title": "Nyhet", "url": "https://example.com/", "date": "2026-02-05"}
    ]
