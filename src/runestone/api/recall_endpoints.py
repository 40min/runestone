"""Authenticated web transport for recall queue management."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.api.recall_schemas import RecallResponse, RecallSettingsUpdate, RecallWordResponse
from runestone.auth.dependencies import get_current_user
from runestone.core.exceptions import (
    InvalidRecallScheduleError,
    RecallOperationError,
    RecallQueueWordNotFoundError,
    RecallStateNotFoundError,
)
from runestone.core.logging_config import get_logger
from runestone.db.database import get_db
from runestone.db.models import User
from runestone.dependencies import get_recall_service
from runestone.recall.service import RecallService
from runestone.recall.types import RecallState
from runestone.utils.timezones import effective_timezone_name

router = APIRouter()
logger = get_logger(__name__)

RECALL_NOT_CONFIGURED_DETAIL = (
    "Recall is not configured. Link your Telegram username in Profile and send /start to the bot."
)


def _response_from_state(state: RecallState | None, timezone_name: object) -> RecallResponse:
    effective_timezone = effective_timezone_name(timezone_name)
    if state is None:
        return RecallResponse(
            configured=False,
            delivery_enabled=False,
            recall_start_hour=9,
            recall_end_hour=22,
            timezone=effective_timezone,
            words=[],
        )

    configured = state.telegram_chat_id is not None
    return RecallResponse(
        configured=configured,
        delivery_enabled=state.is_enabled if configured else False,
        recall_start_hour=state.recall_start_hour,
        recall_end_hour=state.recall_end_hour,
        timezone=effective_timezone,
        words=[
            RecallWordResponse(
                id=word.id,
                word_phrase=word.word_phrase,
                translation=word.translation,
                example_phrase=word.example_phrase,
            )
            for word in state.daily_selection
        ],
    )


async def _run_mutation(
    operation: Callable[[], Awaitable[RecallState]],
    db: AsyncSession,
    user_id: int,
    timezone_name: object,
) -> RecallResponse:
    """Run one recall mutation in the request-owned transaction."""
    try:
        state = await operation()
        response = _response_from_state(state, timezone_name)
        await db.commit()
        return response
    except RecallStateNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=RECALL_NOT_CONFIGURED_DETAIL) from exc
    except RecallQueueWordNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except InvalidRecallScheduleError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid recall delivery schedule") from exc
    except RecallOperationError as exc:
        await db.rollback()
        logger.error("Recall mutation failed for user %s: %s", user_id, exc.details or exc.message)
        raise HTTPException(status_code=500, detail="Failed to update recall selection") from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("Unexpected recall mutation failure for user %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to update recall selection") from exc


@router.get(
    "",
    response_model=RecallResponse,
    responses={
        200: {"description": "Recall configuration and queue retrieved"},
        401: {"description": "Not authenticated"},
        403: {"description": "Inactive account"},
    },
)
async def get_recall(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RecallService, Depends(get_recall_service)],
) -> RecallResponse:
    """Return the authenticated user's recall configuration and ordered queue."""
    try:
        return _response_from_state(await service.get_state_for_user(current_user.id), current_user.timezone)
    except RecallOperationError as exc:
        logger.error("Failed to load recall state for user %s: %s", current_user.id, exc.details or exc.message)
        raise HTTPException(status_code=500, detail="Failed to retrieve recall selection") from exc
    except Exception as exc:
        logger.exception("Unexpected recall read failure for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Failed to retrieve recall selection") from exc


@router.post(
    "/bump",
    response_model=RecallResponse,
    responses={
        200: {"description": "Recall queue refreshed"},
        404: {"description": "Queue word not found"},
        409: {"description": "Recall not configured"},
    },
)
async def bump_recall(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RecallService, Depends(get_recall_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecallResponse:
    """Apply the shared bump workflow and return the authoritative queue."""

    async def operation() -> RecallState:
        return await service.bump_words(current_user.id)

    return await _run_mutation(operation, db, current_user.id, current_user.timezone)


@router.patch(
    "/settings",
    response_model=RecallResponse,
    responses={
        200: {"description": "Recall delivery settings updated"},
        400: {"description": "Invalid recall delivery schedule"},
        409: {"description": "Recall not configured"},
        422: {"description": "Validation error"},
    },
)
async def update_recall_settings(
    update_data: RecallSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RecallService, Depends(get_recall_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecallResponse:
    """Update the authenticated user's configured delivery settings."""

    async def operation() -> RecallState:
        return await service.update_delivery_settings(
            current_user.id,
            update_data.recall_start_hour,
            update_data.recall_end_hour,
            update_data.delivery_enabled,
        )

    return await _run_mutation(operation, db, current_user.id, current_user.timezone)


@router.post(
    "/words/{vocabulary_id}/postpone",
    response_model=RecallResponse,
    responses={
        200: {"description": "Recall word postponed"},
        404: {"description": "Queue word not found"},
        409: {"description": "Recall not configured"},
    },
)
async def postpone_recall_word(
    vocabulary_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RecallService, Depends(get_recall_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecallResponse:
    """Postpone one current queue word by its owned vocabulary id."""
    return await _run_mutation(
        lambda: service.postpone_queue_word(current_user.id, vocabulary_id),
        db,
        current_user.id,
        current_user.timezone,
    )


@router.post(
    "/words/{vocabulary_id}/remove",
    response_model=RecallResponse,
    responses={
        200: {"description": "Recall word removed from learning"},
        404: {"description": "Queue word not found"},
        409: {"description": "Recall not configured"},
    },
)
async def remove_recall_word(
    vocabulary_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[RecallService, Depends(get_recall_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecallResponse:
    """Soft-deactivate one current queue word by its owned vocabulary id."""
    return await _run_mutation(
        lambda: service.remove_queue_word_from_learning(current_user.id, vocabulary_id),
        db,
        current_user.id,
        current_user.timezone,
    )
