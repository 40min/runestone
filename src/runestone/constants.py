"""Shared cross-layer constants."""

from enum import Enum

MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY = 9
MAX_TEACHER_GRAMMAR_SOURCE_LINKS = 2

# Vocabulary priority model (0 = highest, 9 = lowest/default)
VOCABULARY_PRIORITY_HIGH = 0
VOCABULARY_PRIORITY_AGENT_NEW = 4
VOCABULARY_PRIORITY_LEGACY_TRUE_BACKFILL = 5
VOCABULARY_PRIORITY_LOW = 9
VOCABULARY_PRIORITY_DEFAULT = VOCABULARY_PRIORITY_LOW


class TeacherEmotion(str, Enum):
    """Canonical teacher avatar emotions shared across backend layers."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    WORRIED = "worried"
    CONCERNED = "concerned"
    THINKING = "thinking"
    HOPEFUL = "hopeful"
    SURPRISED = "surprised"
    SERIOUS = "serious"


DEFAULT_TEACHER_EMOTION = TeacherEmotion.NEUTRAL
