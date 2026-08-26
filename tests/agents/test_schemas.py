"""Tests for agent schema validation helpers."""

import pytest

from runestone.agents.schemas.chat import ChatMessage, normalize_teacher_emotion
from runestone.agents.schemas.memory import LearningMemorySignal
from runestone.agents.schemas.news import NewsSource
from runestone.agents.schemas.teacher import TeacherOutput
from runestone.constants import DEFAULT_TEACHER_EMOTION, TeacherEmotion


class TestTeacherOutputValidation:
    """Tests for TeacherOutput validation rules."""

    def test_rejects_new_issue_signal_with_memory_id(self):
        """A new_issue signal must not reference an existing memory item."""
        with pytest.raises(ValueError, match="new_issue_cannot_have_memory_id"):
            TeacherOutput(
                message="Good job!",
                learning_memory_signals=[
                    LearningMemorySignal(
                        signal_type="new_issue",
                        summary="Student struggles with articles.",
                        memory_id=42,
                    )
                ],
            )

    def test_deduplicates_learning_memory_signals(self):
        """Duplicate signals are collapsed to the first occurrence."""
        signal = LearningMemorySignal(
            signal_type="improving",
            summary="Articles",
            memory_id=1,
        )
        output = TeacherOutput(
            message="Great!",
            learning_memory_signals=[signal, signal],
        )

        assert output.learning_memory_signals == [signal]

    def test_caps_memory_signals_at_three(self):
        """More than three signals are rejected to keep post-processing bounded."""
        with pytest.raises(ValueError, match="too_many_learning_memory_signals"):
            TeacherOutput(
                message="Lots to track.",
                learning_memory_signals=[
                    LearningMemorySignal(
                        signal_type="improving",
                        summary=f"Area {i}",
                    )
                    for i in range(4)
                ],
            )


class TestChatMessageValidation:
    """Tests for ChatMessage field normalization."""

    def test_deserializes_sources_json_string(self):
        """Sources stored as a JSON string are parsed into NewsSource objects."""
        sources_json = '[{"title": "Nyhet", "url": "https://example.com", ' '"date": "2026-01-01"}]'

        message = ChatMessage(
            role="assistant",
            content="Hej",
            sources=sources_json,
        )

        assert message.sources == [
            NewsSource(
                title="Nyhet",
                url="https://example.com",
                date="2026-01-01",
            )
        ]

    def test_invalid_source_json_becomes_none(self):
        """Malformed source JSON is treated as absent rather than raising."""
        message = ChatMessage(
            role="assistant",
            content="Hej",
            sources="not-json",
        )

        assert message.sources is None

    @pytest.mark.parametrize(
        "raw_emotion,expected",
        [
            ("happy", TeacherEmotion.HAPPY),
            ("  SURPRISED  ", TeacherEmotion.SURPRISED),
            ("unknown_emotion", DEFAULT_TEACHER_EMOTION),
            (None, DEFAULT_TEACHER_EMOTION),
        ],
    )
    def test_normalizes_teacher_emotion(self, raw_emotion, expected):
        """Valid emotions are canonicalized; invalid values fall back to default."""
        assert normalize_teacher_emotion(raw_emotion) is expected

    def test_chat_message_defaults_invalid_emotion(self):
        """ChatMessage applies emotion normalization at validation time."""
        message = ChatMessage(
            role="assistant",
            content="Hej",
            teacher_emotion="not_an_emotion",
        )

        assert message.teacher_emotion is DEFAULT_TEACHER_EMOTION
