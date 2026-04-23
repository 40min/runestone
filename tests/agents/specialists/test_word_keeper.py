from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.word_keeper import (
    WORDKEEPER_SYSTEM_PROMPT,
    SaveCandidate,
    WordKeeperExtraction,
    WordKeeperSpecialist,
)
from runestone.config import Settings


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.word_keeper_provider = "openrouter"
    settings.word_keeper_model = "test-model"
    settings.openrouter_api_key = "test-api-key"
    settings.openai_api_key = "test-openai-key"
    return settings


@pytest.fixture
def mock_chat_model():
    model = MagicMock()
    model.with_structured_output.return_value = AsyncMock()
    return model


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 12
    user.mother_tongue = None
    return user


@pytest.fixture
def specialist(mock_settings, mock_chat_model):
    with patch("runestone.agents.specialists.word_keeper.build_chat_model", return_value=mock_chat_model):
        return WordKeeperSpecialist(mock_settings)


def test_word_keeper_uses_structured_specialist_purpose(mock_settings, mock_chat_model):
    with patch("runestone.agents.specialists.word_keeper.build_chat_model", return_value=mock_chat_model) as mock_build:
        WordKeeperSpecialist(mock_settings)

    mock_build.assert_called_once_with(mock_settings, "word_keeper")


def test_word_keeper_prompt_limits_pre_stage_to_explicit_save_requests():
    assert "### Pre-response phase" in WORDKEEPER_SYSTEM_PROMPT
    assert "Save ONLY when the student explicitly requests it" in (WORDKEEPER_SYSTEM_PROMPT)
    assert (
        "Do NOT save words just because an earlier assistant message in `history` highlighted or introduced them."
        in (WORDKEEPER_SYSTEM_PROMPT)
    )


def test_word_keeper_prompt_uses_teacher_response_as_current_post_stage_signal():
    assert "### Post-response phase" in WORDKEEPER_SYSTEM_PROMPT
    assert "Treat `teacher_response` as the authoritative current teacher message." in (WORDKEEPER_SYSTEM_PROMPT)
    assert "By default, ignore older assistant messages in `history` when deciding what to save." in (
        WORDKEEPER_SYSTEM_PROMPT
    )
    assert "Use older history ONLY when the student explicitly asks to revisit it." in (WORDKEEPER_SYSTEM_PROMPT)


def test_word_keeper_prompt_rejects_exercise_wording_as_save_signal():
    assert "Do NOT treat ordinary exercise wording as a save signal" in WORDKEEPER_SYSTEM_PROMPT
    assert 'Do NOT save words from prompts like "use X or Y in a sentence"' in WORDKEEPER_SYSTEM_PROMPT
    assert "Words that are only mentioned as options in a practice prompt or writing exercise." in (
        WORDKEEPER_SYSTEM_PROMPT
    )
    assert "Bolded words that are emphasized for an exercise but not presented as vocabulary to memorize." in (
        WORDKEEPER_SYSTEM_PROMPT
    )


def test_word_keeper_prompt_standardizes_saved_vocabulary_payloads():
    assert "`word_phrase` — the canonical Swedish learning item" in WORDKEEPER_SYSTEM_PROMPT
    assert "No leading articles: save `hund`, not `en hund`; save `äpple`, not `ett äpple`." in (
        WORDKEEPER_SYSTEM_PROMPT
    )
    assert "Use smart lowercase" in WORDKEEPER_SYSTEM_PROMPT
    assert "Prefer lemma or base form unless the inflected form matters." in WORDKEEPER_SYSTEM_PROMPT
    assert "Do not save bare `att` for verbs" in WORDKEEPER_SYSTEM_PROMPT
    assert "Preserve particles, prepositions, and reflexives that change meaning" in WORDKEEPER_SYSTEM_PROMPT
    assert "Keep Swedish characters; never ASCII-fold `å`, `ä`, or `ö`." in WORDKEEPER_SYSTEM_PROMPT
    assert "Keep translations concise; put morphology and usage in `extra_info`, not `translation`." in (
        WORDKEEPER_SYSTEM_PROMPT
    )


def test_word_keeper_prompt_includes_extra_info_guidance():
    assert "`extra_info` — an optional compact learner note with grammar or usage details." in WORDKEEPER_SYSTEM_PROMPT
    assert "`en-word noun; plural: hundar; definite: hunden`" in WORDKEEPER_SYSTEM_PROMPT
    assert "`verb; infinitive: förstå; present: förstår; past: förstod; supine: förstått`" in (WORDKEEPER_SYSTEM_PROMPT)
    assert 'particle verb; "tycka om" means "to like"' in WORDKEEPER_SYSTEM_PROMPT
    assert "If unsure, leave `extra_info` empty rather than guess." in WORDKEEPER_SYSTEM_PROMPT


def _service_provider(service):
    @asynccontextmanager
    async def _provider():
        yield service

    return _provider


@pytest.mark.anyio
async def test_word_keeper_saves_explicit_request(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="avgorande",
                translation="decisive",
                example_phrase="Det var ett avgorande beslut.",
                extra_info="adjective; common/neuter/plural: avgörande",
                reason="explicit save request",
            )
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock(
        return_value={"action": "created", "word_id": 1, "changed": True}
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save this word for me: avgorande",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "action_taken"
    assert result.actions[0].tool == "prioritize_words_for_learning"
    assert result.artifacts["saved_words"] == ["avgorande"]
    vocabulary_service.upsert_priority_word.assert_awaited_once_with(
        word_phrase="avgorande",
        translation="decisive",
        example_phrase="Det var ett avgorande beslut.",
        extra_info="adjective; common/neuter/plural: avgörande",
        user_id=12,
    )
    assert result.artifacts["save_candidates"][0]["extra_info"] == "adjective; common/neuter/plural: avgörande"


@pytest.mark.anyio
async def test_word_keeper_prefers_chat_fields_for_save_candidate(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="noggrann",
                translation="careful",
                example_phrase="Var noggrann med detaljerna.",
                extra_info="adjective; common: noggrann; neuter: noggrant; plural/definite: noggranna",
                reason="teacher highlighted key words",
            )
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock(
        return_value={"action": "prioritized", "word_id": 2, "changed": True}
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="What does noggrann mean?",
                history=[ChatMessage(role="assistant", content="Noggrann means careful.")],
                user=mock_user,
                teacher_response="The key words here are noggrann. Var noggrann med detaljerna.",
                routing_reason="teacher highlighted key words",
            )
        )

    assert result.status == "action_taken"
    assert result.artifacts["save_candidates"][0]["translation"] == "careful"
    assert result.artifacts["save_candidates"][0]["example_phrase"] == "Var noggrann med detaljerna."
    assert (
        result.artifacts["save_candidates"][0]["extra_info"]
        == "adjective; common: noggrann; neuter: noggrant; plural/definite: noggranna"
    )


@pytest.mark.anyio
async def test_word_keeper_saves_post_response_candidate(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="forutsattning",
                translation="condition",
                example_phrase="En viktig forutsattning ar tid.",
                reason="teacher highlighted key words",
            )
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock(
        return_value={"action": "created", "word_id": 3, "changed": True}
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Explain this word",
                history=[],
                user=mock_user,
                teacher_response="These are good words to memorize: forutsattning.",
                routing_reason="teacher highlighted words to memorize",
            )
        )

    assert result.status == "action_taken"
    vocabulary_service.upsert_priority_word.assert_awaited_once_with(
        word_phrase="forutsattning",
        translation="condition",
        example_phrase="En viktig forutsattning ar tid.",
        extra_info=None,
        user_id=12,
    )


@pytest.mark.anyio
async def test_word_keeper_skips_candidate_with_missing_required_fields(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="forutsattning",
                translation=None,
                example_phrase="En viktig forutsattning ar tid.",
                reason="teacher highlighted key words",
            )
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock()

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Explain this word",
                history=[],
                user=mock_user,
                teacher_response="These are good words to memorize: forutsattning.",
                routing_reason="teacher highlighted words to memorize",
            )
        )

    assert result.status == "no_action"
    assert result.artifacts["saved_words"] == []
    assert result.artifacts["skipped_words"] == [
        {"word_phrase": "forutsattning", "reason": "missing_required_fields_after_completion"}
    ]
    vocabulary_service.upsert_priority_word.assert_not_awaited()


@pytest.mark.anyio
async def test_word_keeper_returns_no_action_when_extractor_finds_none(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    result = await specialist.run(SpecialistContext(message="Hello", history=[], user=mock_user, routing_reason="none"))

    assert result.status == "no_action"
    assert result.artifacts["saved_words"] == []


@pytest.mark.anyio
async def test_word_keeper_returns_error_on_tool_failure(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="avgorande",
                translation="decisive",
                example_phrase="Det var ett avgorande beslut.",
                reason="explicit save request",
            )
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock(side_effect=RuntimeError("db exploded"))

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save this word for me: avgorande",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "error"
    assert result.actions[0].status == "error"


@pytest.mark.anyio
async def test_word_keeper_reports_partial_save_when_later_candidate_fails(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[
            SaveCandidate(
                word_phrase="avgorande",
                translation="decisive",
                example_phrase="Det var ett avgorande beslut.",
                reason="explicit save request",
            ),
            SaveCandidate(
                word_phrase="noggrann",
                translation="careful",
                example_phrase="Var noggrann med detaljerna.",
                reason="explicit save request",
            ),
        ],
    )
    vocabulary_service = MagicMock()
    vocabulary_service.upsert_priority_word = AsyncMock(
        side_effect=[
            {"action": "created", "word_id": 1, "changed": True},
            RuntimeError("db exploded"),
        ]
    )
    vocabulary_service.repo.db.rollback = AsyncMock()

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save these words for me: avgorande, noggrann",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "action_taken"
    assert result.actions[0].status == "success"
    assert result.artifacts["saved_words"] == ["avgorande"]
    assert len(result.artifacts["skipped_words"]) == 1
    assert result.artifacts["skipped_words"][0]["word_phrase"] == "noggrann"
    assert result.artifacts["skipped_words"][0]["reason"].startswith("vocabulary_service_error:")
    assert (
        result.info_for_teacher
        == "Saved 1 vocabulary item(s) for future recall. Skipped 1 item(s) due to internal errors."
    )
    vocabulary_service.repo.db.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_word_keeper_payload_uses_user_mother_tongue(specialist, mock_chat_model, mock_user):
    mock_user.mother_tongue = "Finnish"
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Save this word for me: avgorande",
            history=[],
            user=mock_user,
            routing_reason="explicit save request",
        )
    )

    call_args = mock_llm.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"target_translation_language": "Finnish"' in payload


@pytest.mark.anyio
async def test_word_keeper_payload_defaults_translation_language_to_english(specialist, mock_chat_model, mock_user):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Save this word for me: avgorande",
            history=[],
            user=mock_user,
            routing_reason="explicit save request",
        )
    )

    call_args = mock_llm.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"target_translation_language": "English"' in payload


@pytest.mark.anyio
async def test_word_keeper_post_response_payload_keeps_previous_teacher_message_in_history_but_marks_post_phase(
    specialist, mock_chat_model, mock_user
):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Jag begriper inte.",
            history=[
                ChatMessage(role="user", content="Can you explain these words?"),
                ChatMessage(role="assistant", content="Let's save these words: beskriva, bekräfta."),
            ],
            user=mock_user,
            teacher_response="Let's keep this new word in mind: begripa.",
            routing_reason="teacher highlighted words to memorize",
        )
    )

    call_args = mock_llm.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"phase": "post_response"' in payload
    assert '"teacher_response": "Let\'s keep this new word in mind: begripa."' in payload
    assert '"content": "Let\'s save these words: beskriva, bekräfta."' in payload


@pytest.mark.anyio
async def test_word_keeper_payload_preserves_earlier_history_for_explicit_revisit_request(
    specialist, mock_chat_model, mock_user
):
    mock_llm = mock_chat_model.with_structured_output.return_value
    mock_llm.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Ok, save the words you mentioned before.",
            history=[
                ChatMessage(role="user", content="Can you explain these words?"),
                ChatMessage(role="assistant", content="Let's save these words: beskriva, bekräfta."),
                ChatMessage(role="user", content="Thanks, and one more question."),
                ChatMessage(role="assistant", content="Sure, ask away."),
            ],
            user=mock_user,
            routing_reason="explicit earlier-history save request",
        )
    )

    call_args = mock_llm.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"phase": "pre_response"' in payload
    assert '"message": "Ok, save the words you mentioned before."' in payload
    assert '"content": "Let\'s save these words: beskriva, bekräfta."' in payload
