"""
SQLAlchemy models for the database.

This module defines the database table models using SQLAlchemy ORM.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Vocabulary(Base):
    """Vocabulary table model."""

    __tablename__ = "vocabulary"

    # Fields that can be updated via API
    UPDATABLE_FIELDS = {"word_phrase", "translation", "example_phrase", "in_learn"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    word_phrase = Column(Text, nullable=False, index=True)
    translation = Column(Text, nullable=False)
    example_phrase = Column(Text, nullable=True)
    in_learn = Column(Boolean, default=True)
    last_learned = Column(DateTime(timezone=True), nullable=True)
    learned_times = Column(Integer, default=0, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "word_phrase", name="uq_user_word_phrase"),)
