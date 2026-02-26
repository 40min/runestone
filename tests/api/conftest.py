"""
Shared fixtures and configuration for API tests.

This module provides reusable test fixtures for API testing,
including database setup and test client configuration.
"""

import uuid
from unittest.mock import Mock

import pytest

from runestone.api.main import app
from runestone.auth.dependencies import get_current_user
from runestone.db.models import User
from runestone.dependencies import get_llm_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def client(client_with_overrides):
    """
    Default test client with database access and mock services.
    """
    async for client_obj, _ in client_with_overrides():
        yield client_obj


@pytest.fixture(scope="function")
def mock_llm_client():
    """Create a mock LLM client that doesn't make external API calls."""
    mock_client = Mock()
    # Mock the improve_vocabulary_item method to return a sample response
    mock_client.improve_vocabulary_item.return_value = "Mock extra info for vocabulary enrichment"
    return mock_client


@pytest.fixture(scope="function")
async def client_no_db():
    """Create a test client without database setup for mocked tests."""
    from fastapi import HTTPException, status
    from httpx import ASGITransport, AsyncClient

    from runestone.dependencies import get_chat_service, get_user_service, get_vocabulary_service

    # Mock services to avoid database calls for unauthorized tests
    mock_chat_service = Mock()
    mock_user_service = Mock()
    mock_vocab_service = Mock()

    def override_get_current_user():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    def override_get_chat_service():
        return mock_chat_service

    def override_get_user_service():
        return mock_user_service

    def override_get_vocabulary_service():
        return mock_vocab_service

    # Apply overrides for authentication
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_chat_service] = override_get_chat_service
    app.dependency_overrides[get_user_service] = override_get_user_service
    app.dependency_overrides[get_vocabulary_service] = override_get_vocabulary_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Some tests reach into the underlying FastAPI app to tweak dependency overrides.
        client.app = app
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_with_overrides(mock_llm_client, db_with_test_user):
    """
    Factory fixture for creating test clients with customizable dependency overrides.
    """
    from httpx import ASGITransport, AsyncClient

    from runestone.db.database import get_db
    from runestone.dependencies import get_grammar_service, get_vocabulary_service

    async def _create_client(
        vocabulary_service=None,
        grammar_service=None,
        processor=None,
        llm_client=None,
        current_user=None,
        agent_service=None,
        tts_service=None,
        db_override=None,
    ):
        db, test_user = db_with_test_user

        async def override_get_db():
            """Override database dependency to ensure consistent session use."""
            yield db

        def override_get_llm_client():
            return llm_client or mock_llm_client

        def override_get_current_user():
            return current_user or test_user

        # Apply overrides
        overrides = {
            get_llm_client: override_get_llm_client,
            get_current_user: override_get_current_user,
            get_db: db_override or override_get_db,
        }

        if vocabulary_service:
            overrides[get_vocabulary_service] = lambda: vocabulary_service
        if grammar_service:
            overrides[get_grammar_service] = lambda: grammar_service

        # Always mock RunestoneProcessor
        from unittest.mock import Mock

        from runestone.dependencies import get_runestone_processor

        processor_instance = processor or Mock()
        overrides[get_runestone_processor] = lambda: processor_instance

        if agent_service:
            agent_service_instance = agent_service
        else:
            agent_service_instance = Mock()

        # Always mock TTSService
        from runestone.dependencies import get_tts_service

        tts_service_instance = tts_service or Mock()
        overrides[get_tts_service] = lambda: tts_service_instance

        # Always provide AgentService via dependency + app.state so callers that
        # access request.app.state.* directly don't explode.
        from runestone.dependencies import get_agent_service

        overrides[get_agent_service] = lambda: agent_service_instance

        # Also inject into app.state to avoid attribute errors
        app.state.agent_service = agent_service_instance
        app.state.tts_service = tts_service_instance

        for dep, override in overrides.items():
            app.dependency_overrides[dep] = override

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Some tests reach into the underlying FastAPI app to tweak dependency overrides.
            client.app = app
            client.db = db
            client.user = current_user or test_user

            # Add helper method to ensure database state
            async def sync_db():
                """Sync database to ensure all pending changes are committed and visible."""
                try:
                    if hasattr(db, "is_active") and db.is_active:
                        await db.commit()
                except Exception:
                    pass

            client.sync_db = sync_db

            # Return client and mocks for easy access
            mocks = {
                "vocabulary_service": vocabulary_service,
                "grammar_service": grammar_service,
                "processor": processor,
                "llm_client": llm_client or mock_llm_client,
                "current_user": current_user or test_user,
                "agent_service": agent_service_instance,
                "tts_service": tts_service_instance,
            }

            yield client, mocks

        # Cleanup
        app.dependency_overrides.clear()

    return _create_client


@pytest.fixture(scope="function")
async def client_with_mock_processor(client_with_overrides, mock_processor):
    """
    Create a test client with mocked RunestoneProcessor using the client_with_overrides factory.
    """
    async for client_obj, mocks in client_with_overrides(processor=mock_processor):
        yield client_obj, mocks["processor"]


# ==============================================================================
# Specialized Client Fixtures
# ==============================================================================


@pytest.fixture(scope="function")
async def client_with_mock_vocabulary_service(client_with_overrides, mock_vocabulary_service):
    """
    Create a test client with mocked vocabulary service.
    """
    async for client_obj, mocks in client_with_overrides(vocabulary_service=mock_vocabulary_service):
        yield client_obj, mock_vocabulary_service


@pytest.fixture(scope="function")
async def client_with_mock_grammar_service(client_with_overrides, mock_grammar_service):
    """
    Create a test client with mocked grammar service.
    """
    async for client_obj, mocks in client_with_overrides(grammar_service=mock_grammar_service):
        yield client_obj, mock_grammar_service


@pytest.fixture(scope="function")
async def client_with_mock_agent_service(client_with_overrides, mock_agent_service):
    """
    Create a test client with mocked agent service.
    """
    async for client_obj, mocks in client_with_overrides(agent_service=mock_agent_service):
        yield client_obj, mock_agent_service


# ==============================================================================
# Mock Service Fixtures
# ==============================================================================


@pytest.fixture
def mock_vocabulary_service():
    """Create a standardized mock VocabularyService."""
    from unittest.mock import AsyncMock, Mock

    from runestone.api.schemas import VocabularyImproveResponse

    mock = Mock()
    mock.improve_item = AsyncMock(
        return_value=VocabularyImproveResponse(
            translation="mock translation", example_phrase="mock example", extra_info="mock info"
        )
    )
    mock.save_vocabulary = AsyncMock(return_value={"message": "Vocabulary saved successfully"})
    mock.get_vocabulary = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_grammar_service():
    """Create a standardized mock GrammarService."""
    from unittest.mock import Mock

    mock = Mock()
    mock.list_cheatsheets.return_value = []
    mock.get_cheatsheet_content.return_value = "# Mock Content"
    return mock


@pytest.fixture
def mock_agent_service():
    """Create a standardized mock AgentService."""
    from unittest.mock import AsyncMock

    mock = AsyncMock()
    mock.generate_response.return_value = ("Mock response", None)
    return mock


# ==============================================================================
# Test Data Fixtures
# ==============================================================================


@pytest.fixture
def user_factory(db_session_factory):
    """
    Factory fixture for creating User instances in tests.
    """
    from runestone.auth.security import hash_password

    async def _create_user(**kwargs):
        async with db_session_factory() as db:
            user_data = {
                "email": f"user-{uuid.uuid4()}@example.com",
                "hashed_password": hash_password("password123"),
                "name": "Factory User",
                "surname": "Testsson",
                "timezone": "UTC",
                **kwargs,
            }
            user = User(**user_data)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user

    return _create_user
