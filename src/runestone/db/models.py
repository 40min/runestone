"""
SQLAlchemy models for the database.

This module defines the database table models using SQLAlchemy ORM.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import false

from .database import Base


class User(Base):
    """User table model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=True)
    timezone = Column(String, default="UTC", nullable=False)
    pages_recognised_count = Column(Integer, default=0, nullable=False)
    mother_tongue = Column(String, nullable=True)  # User's preferred language
    # Agent memory fields (stored as JSON strings) - DEPRECATED, use memory_items table
    personal_info = Column(Text, nullable=True)  # Student identity, preferences, goals
    areas_to_improve = Column(Text, nullable=True)  # Recurring struggles and error patterns
    knowledge_strengths = Column(Text, nullable=True)  # Mastered skills and concepts
    memory_migrated = Column(Boolean, server_default=false(), nullable=False)  # Migration flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MemoryItem(Base):
    """Memory item table model for normalized agent memory storage."""

    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "category", "key", name="uq_memory_items_user_category_key"),)


class Vocabulary(Base):
    """Vocabulary table model."""

    __tablename__ = "vocabulary"

    # Fields that can be updated via API
    UPDATABLE_FIELDS = {"word_phrase", "translation", "example_phrase", "extra_info", "in_learn", "priority_learn"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_phrase = Column(Text, nullable=False, index=True)
    translation = Column(Text, nullable=False)
    example_phrase = Column(Text, nullable=True)
    extra_info = Column(Text, nullable=True, default=None)
    in_learn = Column(Boolean, default=True)
    priority_learn = Column(Boolean, default=False, server_default="0")
    last_learned = Column(DateTime(timezone=True), nullable=True)
    learned_times = Column(Integer, default=0, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "word_phrase", name="uq_user_word_phrase"),)


class ChatMessage(Base):
    """Chat message table model."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ChatSummary(Base):
    """Chat summary table model for future compression."""

    __tablename__ = "chat_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    summary_content: Mapped[str] = mapped_column(Text, nullable=False)
    last_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
