"""
Repository for chat message database operations.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from runestone.db.models import ChatMessage


class ChatRepository:
    """Repository for managing chat messages in the database."""

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: Database session
        """
        self.db = db

    def add_message(self, user_id: int, role: str, content: str) -> ChatMessage:
        """
        Add a new chat message to the database.

        Args:
            user_id: ID of the user
            role: Role of the message sender ("user" or "assistant")
            content: Message content

        Returns:
            The created ChatMessage object
        """
        message = ChatMessage(user_id=user_id, role=role, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_raw_history(self, user_id: int) -> List[ChatMessage]:
        """
        Fetch all chat messages for a user, ordered by creation time.

        Args:
            user_id: ID of the user

        Returns:
            List of ChatMessage objects
        """
        stmt = select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_context_for_agent(self, user_id: int, limit: int = 20) -> List[ChatMessage]:
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
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(self.db.execute(stmt).scalars().all())
        # Return in chronological order
        return sorted(messages, key=lambda x: x.created_at)

    def truncate_history(self, user_id: int, retention_days: int):
        """
        Delete messages older than the retention threshold.

        Args:
            user_id: ID of the user
            retention_days: Number of days to keep messages
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id, ChatMessage.created_at < threshold)
        self.db.execute(stmt)
        self.db.commit()

    def clear_all_history(self, user_id: int):
        """
        Delete all chat messages for a user.

        Args:
            user_id: ID of the user
        """
        stmt = delete(ChatMessage).where(ChatMessage.user_id == user_id)
        self.db.execute(stmt)
        self.db.commit()
