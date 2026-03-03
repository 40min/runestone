import json
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from runestone.db.models import ChatMessage


class ChatRepository:
    """Repository for managing chat messages in the database."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the repository.

        Args:
            db: Database session
        """
        self.db = db

    async def add_message(
        self,
        user_id: int,
        chat_id: str,
        role: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> ChatMessage:
        """
        Add a new chat message to the database.

        Args:
            user_id: ID of the user
            chat_id: Chat session identifier
            role: Role of the message sender ("user" or "assistant")
            content: Message content

        Returns:
            The created ChatMessage object
        """
        message = ChatMessage(
            user_id=user_id,
            chat_id=chat_id,
            role=role,
            content=content,
            sources=json.dumps(sources) if sources else None,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_raw_history(self, user_id: int, chat_id: str) -> List[ChatMessage]:
        """
        Fetch all chat messages for a user, ordered by creation time.

        Args:
            user_id: ID of the user

        Returns:
            List of ChatMessage objects
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id, ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_context_for_agent(self, user_id: int, chat_id: str, limit: int = 20) -> List[ChatMessage]:
        """
        Fetch the most recent chat messages for the agent context.

        Args:
            user_id: ID of the user
            limit: Maximum number of messages to fetch

        Returns:
            List of ChatMessage objects
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id, ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        # Return in chronological order
        return sorted(messages, key=lambda x: x.created_at)

    async def get_history_after_id(
        self, user_id: int, chat_id: str, after_id: int = 0, limit: int = 200
    ) -> List[ChatMessage]:
        """
        Fetch chat messages for a user/chat session with optional incremental filtering.

        Args:
            user_id: ID of the user
            chat_id: Chat session ID
            after_id: Return only messages with id greater than this value
            limit: Maximum number of messages

        Returns:
            List of ChatMessage objects in chronological order
        """
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.chat_id == chat_id,
                ChatMessage.id > after_id,
            )
            .order_by(ChatMessage.id.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_id(self, user_id: int, chat_id: str) -> int:
        """
        Get the latest message id for the given user/chat session.

        Returns:
            Latest message id or 0 when chat is empty
        """
        stmt = select(func.max(ChatMessage.id)).where(ChatMessage.user_id == user_id, ChatMessage.chat_id == chat_id)
        result = await self.db.execute(stmt)
        res = result.scalar_one_or_none()
        return int(res or 0)

    async def get_oldest_id(self, user_id: int, chat_id: str) -> int:
        """
        Get the oldest message id for the given user/chat session.

        Returns:
            Oldest message id or 0 when chat is empty
        """
        stmt = select(func.min(ChatMessage.id)).where(ChatMessage.user_id == user_id, ChatMessage.chat_id == chat_id)
        result = await self.db.execute(stmt)
        res = result.scalar_one_or_none()
        return int(res or 0)

    async def truncate_history(self, user_id: int, retention_days: int, preserve_chat_id: str | None = None):
        """
        Delete messages older than the retention threshold.

        Args:
            user_id: ID of the user
            retention_days: Number of days to keep messages
            preserve_chat_id: Optional chat ID to exclude from truncation
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id, ChatMessage.created_at < threshold)
        if preserve_chat_id:
            stmt = stmt.where(ChatMessage.chat_id != preserve_chat_id)
        await self.db.execute(stmt)
        await self.db.commit()

    async def clear_all_history(self, user_id: int):
        """
        Delete all chat messages for a user.

        Args:
            user_id: ID of the user
        """
        stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id)
        await self.db.execute(stmt)
        await self.db.commit()
