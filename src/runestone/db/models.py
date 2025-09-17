"""
SQLAlchemy models for the database.

This module defines the database table models using SQLAlchemy ORM.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, Text
from sqlalchemy.sql import func

from .database import Base


class Vocabulary(Base):
    """Vocabulary table model."""

    __tablename__ = "vocabulary"

    # Fields that can be updated via API
    UPDATABLE_FIELDS = {"word_phrase", "translation", "example_phrase", "in_learn"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    word_phrase = Column(Text, nullable=False, unique=True, index=True)
    translation = Column(Text, nullable=False)
    example_phrase = Column(Text, nullable=True)
    in_learn = Column(Boolean, default=True)
    showed_times = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
