"""Shared cross-layer constants."""

from enum import Enum

MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY = 9
MAX_TEACHER_GRAMMAR_SOURCE_LINKS = 2
MAX_GRAMMAR_SEARCH_CALLS = 1
MAX_GRAMMAR_READ_CALLS = 10

# Specialist recursion limits to prevent runaway tool loops
RECURSION_LIMIT_NEWS_AGENT = 20
RECURSION_LIMIT_MEMORY_MAINTAINER = 250
RECURSION_LIMIT_TEACHER = 30

# Vocabulary priority model (0 = highest, 9 = lowest/default)
VOCABULARY_PRIORITY_HIGH = 0
VOCABULARY_PRIORITY_AGENT_NEW = 4
VOCABULARY_PRIORITY_LEGACY_TRUE_BACKFILL = 5
VOCABULARY_PRIORITY_LOW = 9
VOCABULARY_PRIORITY_DEFAULT = VOCABULARY_PRIORITY_LOW

# Human-readable labels for vocabulary priority values (0 = highest, 9 = lowest/default).
# The service layer uses this mapping when building distribution responses.
VOCABULARY_PRIORITY_LABELS: dict[int, str] = {
    0: "Highest (0)",
    1: "Very High (1)",
    2: "High (2)",
    3: "Above Average (3)",
    4: "Average (4)",
    5: "Below Average (5)",
    6: "Low (6)",
    7: "Very Low (7)",
    8: "Minimal (8)",
    9: "Default (9)",
}


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
