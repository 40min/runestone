"""
SQLAlchemy models for the database.

This module defines the database table models using SQLAlchemy ORM.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Vocabulary(Base):
    """Vocabulary table model."""

    __tablename__ = "vocabulary"

    # Fields that can be updated via API
    UPDATABLE_FIELDS = {"word_phrase", "translation", "example_phrase", "extra_info", "in_learn"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_phrase = Column(Text, nullable=False, index=True)
    translation = Column(Text, nullable=False)
    example_phrase = Column(Text, nullable=True)
    extra_info = Column(Text, nullable=True, default=None)
    in_learn = Column(Boolean, default=True)
    last_learned = Column(DateTime(timezone=True), nullable=True)
    learned_times = Column(Integer, default=0, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "word_phrase", name="uq_user_word_phrase"),)
