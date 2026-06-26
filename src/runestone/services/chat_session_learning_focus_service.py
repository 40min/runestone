"""Service for session-scoped frozen learning-focus selection and cleanup."""

import json

from runestone.api.memory_item_schemas import AreaToImproveStatus, MemoryCategory, MemoryItemResponse
from runestone.core.logging_config import get_logger
from runestone.db.chat_session_learning_focus_repository import ChatSessionLearningFocusRepository
from runestone.db.models import MemoryItem
from runestone.services.memory_item_service import MemoryItemService

logger = get_logger(__name__)


class ChatSessionLearningFocusService:
    """Own the frozen-per-chat learning-focus lifecycle for Teacher context."""

    def __init__(
        self,
        repository: ChatSessionLearningFocusRepository,
        memory_item_service: MemoryItemService,
    ):
        """Initialize service with persistence and memory-item collaborators."""
        self.repo = repository
        self.memory_item_service = memory_item_service

    async def get_chat_session_learning_focus(
        self,
        user_id: int,
        chat_id: str,
        area_limit: int,
    ) -> tuple[list[MemoryItemResponse], bool]:
        """Return the stable ordered learning-focus batch and whether it was reseeded."""
        focus = await self.repo.get_by_user_chat(user_id, chat_id)
        if focus is None:
            return await self._reseed_chat_session_learning_focus(
                user_id=user_id,
                chat_id=chat_id,
                area_limit=area_limit,
            )

        stored_item_ids = self._decode_focus_item_ids(focus.memory_item_ids_json)
        if stored_item_ids is None:
            return await self._reseed_chat_session_learning_focus(
                user_id=user_id,
                chat_id=chat_id,
                area_limit=area_limit,
            )

        hydrated_items, missing_ids = await self._hydrate_chat_session_learning_focus(
            user_id=user_id,
            stored_item_ids=stored_item_ids,
        )

        if stored_item_ids and not hydrated_items:
            return await self._reseed_chat_session_learning_focus(
                user_id=user_id,
                chat_id=chat_id,
                area_limit=area_limit,
                reseeded=True,
            )

        if hydrated_items and all(item.status == AreaToImproveStatus.MASTERED.value for item in hydrated_items):
            return await self._reseed_chat_session_learning_focus(
                user_id=user_id,
                chat_id=chat_id,
                area_limit=area_limit,
                reseeded=True,
            )

        if missing_ids:
            logger.warning(
                "chat-session learning focus drifted for user_id=%s chat_id=%s missing_item_ids=%s",
                user_id,
                chat_id,
                missing_ids,
            )
            await self.repo.upsert_item_ids(
                chat_id=chat_id,
                user_id=user_id,
                item_ids=[item.id for item in hydrated_items],
            )

        return (
            [MemoryItemResponse.model_validate(item) for item in hydrated_items],
            False,
        )

    async def cleanup_old_chat_session_learning_focus(self, user_id: int, preserve_chat_id: str) -> int:
        """Delete frozen learning-focus rows from older chat sessions for one user."""
        return await self.repo.delete_for_user_except_chat(user_id, preserve_chat_id)

    def _decode_focus_item_ids(self, memory_item_ids_json: str) -> list[int] | None:
        """Parse persisted ordered memory ids, returning None on decode error."""
        try:
            raw_ids = json.loads(memory_item_ids_json)
        except json.JSONDecodeError:
            logger.warning("failed to decode chat-session learning focus ids json=%r", memory_item_ids_json)
            return None

        if not isinstance(raw_ids, list):
            return None

        item_ids: list[int] = []
        for raw_id in raw_ids:
            if isinstance(raw_id, int):
                item_ids.append(raw_id)
        return item_ids

    async def _hydrate_chat_session_learning_focus(
        self,
        *,
        user_id: int,
        stored_item_ids: list[int],
    ) -> tuple[list[MemoryItem], list[int]]:
        """Reload stored ids in order while dropping rows that no longer resolve cleanly."""
        rows = await self.memory_item_service.get_items_by_ids(stored_item_ids)
        rows_by_id = {
            row.id: row
            for row in rows
            if row.user_id == user_id and row.category == MemoryCategory.AREA_TO_IMPROVE.value
        }
        hydrated_items = [rows_by_id[item_id] for item_id in stored_item_ids if item_id in rows_by_id]
        missing_ids = [item_id for item_id in stored_item_ids if item_id not in rows_by_id]
        return hydrated_items, missing_ids

    async def _reseed_chat_session_learning_focus(
        self,
        *,
        user_id: int,
        chat_id: str,
        area_limit: int,
        reseeded: bool = False,
    ) -> tuple[list[MemoryItemResponse], bool]:
        """Select and persist a fresh ordered batch for the active chat session."""
        starter_items = await self.memory_item_service.list_start_area_to_improve_items(user_id, area_limit)
        await self.repo.upsert_item_ids(
            user_id=user_id,
            chat_id=chat_id,
            item_ids=[item.id for item in starter_items],
        )
        return starter_items, reseeded
