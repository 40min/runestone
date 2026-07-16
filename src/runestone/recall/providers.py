"""Recall service providers with explicit transaction ownership modes."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from runestone.config import settings
from runestone.core.service_llm import build_service_llm_model
from runestone.db.database import provide_db_session
from runestone.db.recall_repository import RecallRepository
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.recall.service import RecallService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_service_llm_model():
    """Reuse the stateless service model across short-lived recall sessions."""
    return build_service_llm_model(settings)


def _create_recall_service(session: AsyncSession) -> RecallService:
    """Assemble the required recall graph over one supplied session."""
    vocabulary_service = VocabularyService(
        VocabularyRepository(session),
        settings,
        _get_service_llm_model(),
    )
    user_service = UserService(UserRepository(session))
    return RecallService(
        RecallRepository(session),
        vocabulary_service,
        user_service,
        settings,
    )


@asynccontextmanager
async def provide_recall_transaction() -> AsyncIterator[RecallService]:
    """Yield a recall service inside one provider-owned transaction.

    Normal exit commits exactly once through SQLAlchemy's outer transaction
    context. Exceptional exit rolls back exactly once before the fresh session
    is closed.
    """
    transaction_committed = False
    try:
        async with provide_db_session() as session:
            async with session.begin():
                yield _create_recall_service(session)
            transaction_committed = True
    except Exception:
        if not transaction_committed:
            raise
        # Application work is already durable. A later session-close failure
        # must not suppress its prepared response or replay the command.
        logger.exception("Failed to close recall command session after commit")


@asynccontextmanager
async def provide_recall_session() -> AsyncIterator[RecallService]:
    """Yield a recall service with a fresh session but no owned application commit.

    Scheduled delivery uses this mode because ``deliver_next_word`` owns its
    callback-spanning commit or rollback lifecycle.
    """
    async with provide_db_session() as session:
        yield _create_recall_service(session)
