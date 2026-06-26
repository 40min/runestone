import json
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.db.models import ChatSessionLearningFocus


class ChatSessionLearningFocusRepository:
    """Repository for chat-session-scoped frozen learning-focus batches."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_by_user_chat(self, user_id: int, chat_id: str) -> Optional[ChatSessionLearningFocus]:
        """Return one chat-session focus row for the user and chat."""
        stmt = select(ChatSessionLearningFocus).where(
            ChatSessionLearningFocus.user_id == user_id,
            ChatSessionLearningFocus.chat_id == chat_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def upsert_item_ids(self, user_id: int, chat_id: str, item_ids: list[int]) -> ChatSessionLearningFocus:
        """Create or update the frozen ordered item ids for one chat session."""
        focus = await self.get_by_user_chat(user_id, chat_id)
        serialized_ids = json.dumps(item_ids)
        if focus is None:
            focus = ChatSessionLearningFocus(
                user_id=user_id,
                chat_id=chat_id,
                memory_item_ids_json=serialized_ids,
            )
            self.db.add(focus)
        else:
            focus.memory_item_ids_json = serialized_ids

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            focus = await self.get_by_user_chat(user_id, chat_id)
            if focus is None:
                raise
        await self.db.refresh(focus)
        return focus

    async def delete_for_user_except_chat(self, user_id: int, preserve_chat_id: str) -> int:
        """Delete all session-focus rows for the user except the active chat id."""
        stmt = delete(ChatSessionLearningFocus).where(
            ChatSessionLearningFocus.user_id == user_id,
            ChatSessionLearningFocus.chat_id != preserve_chat_id,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount or 0
