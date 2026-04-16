"""
Tests for ChatService.
"""

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from runestone.db.chat_repository import ChatRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.chat_service import ChatService


@pytest.fixture
def mock_agent_service():
    """Create a mock AgentsManager."""
    mock = AsyncMock()
    mock.process_turn_result = ("Björn's reply", None, "neutral")
    mock.process_turn.side_effect = lambda **_kwargs: mock.process_turn_result
    return mock


@pytest.fixture
def mock_vocabulary_service():
    """Create a mock VocabularyService."""
    return Mock()


@pytest.fixture
def mock_tts_service():
    """Create a mock TTSService."""
    mock = Mock()
    mock.push_audio_to_client = AsyncMock()
    return mock


@pytest.fixture
def mock_user_service():
    """Create a mock UserService."""
    mock = Mock()
    # Setup default mock behavior
    mock_user = Mock()
    mock_user.id = 1
    mock_user.current_chat_id = str(uuid4())
    mock.get_user_by_id = AsyncMock(return_value=mock_user)
    mock.get_or_create_current_chat_id = AsyncMock(return_value=mock_user.current_chat_id)
    mock.rotate_current_chat_id = AsyncMock(return_value=str(uuid4()))

    mock_profile = Mock()
    mock_profile.personal_info = None
    mock_profile.areas_to_improve = None
    mock_profile.knowledge_strengths = None
    mock.get_user_profile = AsyncMock(return_value=mock_profile)
    return mock


@pytest.fixture
def mock_memory_item_service():
    """Create a mock MemoryItemService."""
    return Mock()


@pytest.fixture
def mock_processor():
    """Create a mock RunestoneProcessor."""
    mock = AsyncMock()
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
    # Use a real service but maybe mock the repo within it if needed?
    # For now, let's mock the service itself to simplify orchestration tests.
    side_effect_service = MagicMock(spec=AgentSideEffectService)
    side_effect_service.create_post_coordinator_row = AsyncMock(return_value=42)
    side_effect_service.load_latest_coordinator_row = AsyncMock(return_value=None)

    mock_settings = Mock()
    mock_settings.chat_history_retention_days = 7
    return ChatService(
        mock_settings,
        repository,
        side_effect_service,
        mock_user_service,
        mock_agent_service,
        mock_processor,
        mock_vocabulary_service,
        mock_tts_service,
        mock_memory_item_service,
    )


@pytest.mark.anyio
async def test_process_message_orchestration(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test the full flow of processing a message with the new stage orchestration."""
    db, user = db_with_test_user

    # Configure mock user service to return the DB user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    response, sources, teacher_emotion = await chat_service.process_message(user.id, "Hej Björn")

    assert response == "Björn's reply"
    assert sources is None
    assert teacher_emotion == "neutral"

    # Verify persistence
    history = await chat_service.get_history(user.id, user.current_chat_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hej Björn"
    assert history[1].role == "assistant"
    assert history[1].content == "Björn's reply"
    assert history[1].teacher_emotion == "neutral"

    # Verify new 3-stage orchestration
    mock_agent_service.process_turn.assert_called_once()
    kwargs = mock_agent_service.process_turn.call_args.kwargs
    assert "chat_repository" not in kwargs
    assert "tts_service" not in kwargs


@pytest.mark.anyio
async def test_process_message_with_history(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test process_message when there is existing history."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    # Add some history
    await chat_service.process_message(user.id, "Message 1")
    mock_agent_service.process_turn.reset_mock()

    # Process second message
    await chat_service.process_message(user.id, "Message 2")

    mock_agent_service.process_turn.assert_called_once()
    kwargs = mock_agent_service.process_turn.call_args.kwargs

    assert kwargs["message"] == "Message 2"
    history = kwargs["history"]
    assert len(history) == 2
    assert history[0].content == "Message 1"
    assert history[1].content == "Björn's reply"


@pytest.mark.anyio
async def test_process_message_logs_total_turn_timing(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, caplog
):
    """Test overall chat turn timing is logged."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    with caplog.at_level("INFO"):
        await chat_service.process_message(user.id, "Hej Björn")

    assert "[chat:service] Message turn completed" in caplog.text
    assert "latency_ms=" in caplog.text
    assert f"user_id={user.id}" in caplog.text
    assert "message_chars=9" in caplog.text


@pytest.mark.anyio
async def test_process_image_message_success(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, mock_processor
):
    """Test successful image processing with async post treatment."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    # Configure processor mock for this test
    ocr_result = Mock()
    ocr_result.transcribed_text = "Hej. Hur mår du?"
    mock_processor.run_ocr.return_value = ocr_result

    # Process image
    response, teacher_emotion = await chat_service.process_image_message(user.id, b"fake_image_bytes")

    assert response == "Björn's reply"
    assert teacher_emotion == "neutral"
    mock_processor.run_ocr.assert_called_once_with(b"fake_image_bytes")

    # Verify orchestration
    mock_agent_service.process_turn.assert_called_once()

    history = await chat_service.get_history(user.id, user.current_chat_id)
    assert history[-1].role == "assistant"
    assert history[-1].content == "Björn's reply"


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
    mock_agent_service.process_turn.assert_called_once()
    kwargs = mock_agent_service.process_turn.call_args.kwargs
    prompt = kwargs["message"]

    # Verify Spanish is mentioned in the prompt
    assert "Spanish" in prompt
    assert "Hej världen" in prompt


@pytest.mark.anyio
async def test_clear_history(chat_service, db_with_test_user):
    """Test clearing history via service."""
    db, user = db_with_test_user
    chat_id = str(uuid4())
    await chat_service.repository.add_message(user.id, chat_id, "user", "Test")
    chat_service.user_service.rotate_current_chat_id = AsyncMock(return_value=str(uuid4()))
    await chat_service.clear_history(user.id)
    chat_service.user_service.rotate_current_chat_id.assert_awaited_once_with(user.id)


@pytest.mark.anyio
async def test_process_message_persists_sources(chat_service, db_with_test_user, mock_agent_service, mock_user_service):
    """Test that sources are stored and returned in history."""
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id
    mock_agent_service.process_turn_result = (
        "Svar med källor",
        [{"title": "Nyhet", "url": "https://example.com", "date": "2026-02-05"}],
        "neutral",
    )

    await chat_service.process_message(user.id, "Nyheter tack")

    history = await chat_service.get_history(user.id, user.current_chat_id)
    assistant_messages = [msg for msg in history if msg.role == "assistant"]
    assert len(assistant_messages) == 1
    # Note: URL might be normalized with trailing slash depending on Pydantic's AnyHttpUrl behavior in history load
    sources = [s.model_dump(mode="json") for s in assistant_messages[0].sources]
    assert sources[0]["title"] == "Nyhet"
    assert "example.com" in sources[0]["url"]


@pytest.mark.anyio
async def test_process_message_pushes_tts_from_chat_service(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, mock_tts_service
):
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id
    mock_agent_service.process_turn_result = ("Ljudsvar", None, "neutral")

    response, _sources, _teacher_emotion = await chat_service.process_message(
        user.id, "Säg det högt", tts_expected=True, speed=1.25
    )

    assert response == "Ljudsvar"
    mock_tts_service.push_audio_to_client.assert_awaited_once_with(user.id, "Ljudsvar", speed=1.25)


@pytest.mark.anyio
async def test_process_message_persists_teacher_emotion(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service
):
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id
    mock_agent_service.process_turn_result = ("Bra jobbat!", None, "happy")

    response, _sources, teacher_emotion = await chat_service.process_message(user.id, "Jag klarade det")

    history = await chat_service.get_history(user.id, user.current_chat_id)
    assistant_messages = [msg for msg in history if msg.role == "assistant"]
    assert response == "Bra jobbat!"
    assert teacher_emotion == "happy"
    assert assistant_messages[0].teacher_emotion == "happy"


@pytest.mark.anyio
async def test_process_image_message_delegates_stale_post_task_check_when_history_exists(
    chat_service, db_with_test_user, mock_agent_service, mock_user_service, mock_processor
):
    db, user = db_with_test_user
    user.current_chat_id = str(uuid4())
    mock_user_service.get_user_by_id.return_value = user
    mock_user_service.get_or_create_current_chat_id.return_value = user.current_chat_id

    await chat_service.repository.add_message(user.id, user.current_chat_id, "assistant", "Earlier reply")

    ocr_result = Mock()
    ocr_result.transcribed_text = "Hej igen"
    mock_processor.run_ocr.return_value = ocr_result

    await chat_service.process_image_message(user.id, b"fake_image_bytes")

    mock_agent_service.process_turn.assert_called_once()
    kwargs = mock_agent_service.process_turn.call_args.kwargs
    assert kwargs["history"][0].content == "Earlier reply"
