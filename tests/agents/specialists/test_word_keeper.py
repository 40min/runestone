import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runestone.agents.schemas import ChatMessage
from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.word_keeper import (
    WORDKEEPER_ENRICHMENT_PROMPT,
    WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT,
    WordEnrichmentItem,
    WordKeeperEnrichment,
    WordKeeperExtraction,
    WordKeeperSpecialist,
)
from runestone.config import Settings
from runestone.schemas.vocabulary_save import VocabularyPrioritizationAction, WordSaveCandidate


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
    model.extraction_model = AsyncMock()
    model.enrichment_model = AsyncMock()

    def _structured_model(schema):
        if schema is WordKeeperExtraction:
            return model.extraction_model
        if schema is WordKeeperEnrichment:
            return model.enrichment_model
        raise AssertionError(f"Unexpected schema: {schema}")

    model.with_structured_output.side_effect = _structured_model
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


def _service_provider(service):
    @asynccontextmanager
    async def _provider():
        yield service

    return _provider


def _mock_vocabulary_service(priority_actions=None, upsert_return=None, upsert_side_effect=None):
    service = MagicMock()
    service.prepare_priority_word_save = AsyncMock(return_value=priority_actions or [])
    if upsert_return is None:
        batch_return = [{"action": "created", "word_id": 1}]
    elif isinstance(upsert_return, dict):
        batch_return = [upsert_return]
    else:
        batch_return = upsert_return
    service.insert_or_prioritize_words = AsyncMock(return_value=batch_return)
    if upsert_side_effect is not None:
        service.insert_or_prioritize_words.side_effect = upsert_side_effect
    service.repo.db.rollback = AsyncMock()
    return service


def _priority_actions(*entries):
    return [
        VocabularyPrioritizationAction(
            candidate_id=str(index),
            word_phrase=word_phrase,
            source_form=source_form,
            context_phrase=context_phrase,
            action=action,
            word_id=word_id,
            changed=changed,
        )
        for index, (word_phrase, action, word_id, changed, source_form, context_phrase) in enumerate(entries)
    ]


def _priority_entry(word_phrase, action, word_id=1, changed=True, source_form=None, context_phrase=None):
    return word_phrase, action, word_id, changed, source_form, context_phrase


def test_word_keeper_uses_structured_specialist_purpose(mock_settings, mock_chat_model):
    with patch("runestone.agents.specialists.word_keeper.build_chat_model", return_value=mock_chat_model) as mock_build:
        WordKeeperSpecialist(mock_settings)

    mock_build.assert_called_once_with(mock_settings, "word_keeper")


def test_word_keeper_prompt_limits_pre_stage_to_explicit_save_requests():
    assert "## Request Scope" in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    assert "Evaluate `message` as the active save request." in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    assert "you may use `teacher_response` only to resolve the immediately preceding teacher context" in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )
    assert "Return candidates only if `message` explicitly asks to save vocabulary" in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )


def test_word_keeper_prompt_is_pre_response_only():
    assert "teacher_response" in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    assert "post-response" not in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    assert "immediately preceding teacher context" in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT


def test_word_keeper_prompt_rejects_exercise_wording_as_save_signal():
    assert "Words that are only mentioned as options in a practice prompt or writing exercise." in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )
    assert "Bolded words that are emphasized for an exercise but not presented as vocabulary to memorize." in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )


def test_word_keeper_prompt_saves_corrected_word_not_misspelling():
    assert "Misspelled, invalid, or nonexistent student-written word forms" in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )
    assert "the corrected target item" in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT


def test_word_keeper_extraction_schema_is_key_only():
    fields = WordSaveCandidate.model_fields
    assert set(fields) == {"word_phrase", "source_form", "context_phrase"}
    assert "Do not generate translations, examples, grammar notes, or reasons." in (
        WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT
    )
    assert "generate a short, natural Swedish" in WORDKEEPER_SAVE_REQUEST_EXTRACTION_PROMPT


def test_word_keeper_enrichment_prompt_owns_full_save_fields():
    assert "`candidate_id`" in WORDKEEPER_ENRICHMENT_PROMPT
    assert "`translation`" in WORDKEEPER_ENRICHMENT_PROMPT
    assert "`example_phrase`" in WORDKEEPER_ENRICHMENT_PROMPT
    assert "`extra_info`" in WORDKEEPER_ENRICHMENT_PROMPT
    assert "`en-word noun; plural: hundar; definite: hunden`" in WORDKEEPER_ENRICHMENT_PROMPT
    assert "If unsure, leave `extra_info` empty rather than guess." in WORDKEEPER_ENRICHMENT_PROMPT
    assert "`translation` and `example_phrase` should be filled whenever reasonably possible." in (
        WORDKEEPER_ENRICHMENT_PROMPT
    )
    assert "teacher_response" not in WORDKEEPER_ENRICHMENT_PROMPT


def test_word_keeper_models_decode_double_escaped_unicode():
    candidate = WordSaveCandidate(word_phrase="avg\\u00f6rande", source_form="avg\\u00f6rande")
    enrichment = WordEnrichmentItem(
        candidate_id="0",
        word_phrase="avg\\u00f6rande",
        translation="decisive",
        example_phrase="Det var ett avg\\u00f6rande beslut.",
        extra_info="adjective; common/neuter/plural: avg\\u00f6rande",
    )

    assert candidate.word_phrase == "avgörande"
    assert candidate.source_form == "avgörande"
    assert enrichment.word_phrase == "avgörande"
    assert enrichment.example_phrase == "Det var ett avgörande beslut."
    assert enrichment.extra_info == "adjective; common/neuter/plural: avgörande"


def test_word_keeper_models_preserve_existing_unicode_when_decoding_escapes():
    candidate = WordSaveCandidate(word_phrase="Här \\u00f6ver", source_form="Här \\u00f6ver")
    enrichment = WordEnrichmentItem(
        candidate_id="0",
        word_phrase="Här \\u00f6ver",
        translation="over here",
        example_phrase="Här \\u00f6ver finns svaret.",
        extra_info="phrase; mixed decoded and escaped unicode",
    )

    assert candidate.word_phrase == "Här över"
    assert candidate.source_form == "Här över"
    assert enrichment.word_phrase == "Här över"
    assert enrichment.example_phrase == "Här över finns svaret."


def test_word_keeper_models_decode_double_escaped_non_bmp_unicode():
    candidate = WordSaveCandidate(word_phrase="glad \\U0001f600", source_form="glad \\U0001f600")
    enrichment = WordEnrichmentItem(
        candidate_id="0",
        word_phrase="glad \\U0001f600",
        translation="happy",
        example_phrase="Hon blev glad \\U0001f600.",
        extra_info="adjective; handles non-BMP escapes",
    )

    assert candidate.word_phrase == "glad 😀"
    assert candidate.source_form == "glad 😀"
    assert enrichment.word_phrase == "glad 😀"
    assert enrichment.example_phrase == "Hon blev glad 😀."


@pytest.mark.anyio
async def test_word_keeper_prioritizes_existing_without_enrichment(specialist, mock_chat_model, mock_user):
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(_priority_entry("noggrann", "prioritized", word_id=2))
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
                teacher_response="The key words here are noggrann.",
                vocabulary_candidates=[WordSaveCandidate(word_phrase="noggrann")],
                routing_reason="teacher emitted vocabulary_candidates",
            )
        )

    assert result.status == "action_taken"
    mock_chat_model.extraction_model.ainvoke.assert_not_awaited()
    assert result.artifacts["saved_words"] == ["noggrann"]
    assert result.artifacts["action_counts"]["prioritized"] == 1
    assert result.artifacts["priority_actions"][0]["action"] == "prioritized"
    priority_candidates = vocabulary_service.prepare_priority_word_save.call_args[0][0]
    assert [candidate.word_phrase for candidate in priority_candidates] == ["noggrann"]
    vocabulary_service.prepare_priority_word_save.assert_awaited_once()
    vocabulary_service.insert_or_prioritize_words.assert_not_awaited()
    mock_chat_model.enrichment_model.ainvoke.assert_not_awaited()


@pytest.mark.anyio
async def test_word_keeper_enriches_and_saves_new_word(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[WordSaveCandidate(word_phrase="avgörande")],
    )
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="avgörande",
                translation="decisive",
                example_phrase="Det var ett avgörande beslut.",
                extra_info="adjective; common/neuter/plural: avgörande",
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(_priority_entry("avgörande", "missing", word_id=None, changed=False)),
        upsert_return={"action": "created", "word_id": 3, "changed": True},
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save this word for me: avgörande",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "action_taken"
    assert result.artifacts["saved_words"] == ["avgörande"]
    assert result.artifacts["action_counts"]["created"] == 1
    vocabulary_service.insert_or_prioritize_words.assert_awaited_once()
    items = vocabulary_service.insert_or_prioritize_words.call_args.args[0]
    assert [item.model_dump() for item in items] == [
        {
            "word_phrase": "avgörande",
            "translation": "decisive",
            "example_phrase": "Det var ett avgörande beslut.",
            "extra_info": "adjective; common/neuter/plural: avgörande",
            "in_learn": True,
            "priority_learn": 9,
        }
    ]
    assert vocabulary_service.insert_or_prioritize_words.call_args.kwargs == {"user_id": 12}


@pytest.mark.anyio
async def test_word_keeper_direct_candidates_skip_extraction_and_reach_enrichment(
    specialist, mock_chat_model, mock_user
):
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="begripa",
                translation="understand",
                example_phrase="Jag begriper inte.",
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(
            _priority_entry(
                "begripa",
                "missing",
                word_id=None,
                changed=False,
                source_form="begriper",
                context_phrase="Jag begriper inte.",
            )
        ),
        upsert_return={"action": "created", "word_id": 3, "changed": True},
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Jag begriper inte.",
                history=[],
                user=mock_user,
                teacher_response="Good sentence. Let's keep begripa in mind.",
                vocabulary_candidates=[
                    WordSaveCandidate(
                        word_phrase="begripa",
                        source_form="begriper",
                        context_phrase="Jag begriper inte.",
                    )
                ],
                routing_reason="teacher emitted vocabulary_candidates",
            )
        )

    assert result.status == "action_taken"
    mock_chat_model.extraction_model.ainvoke.assert_not_awaited()
    priority_candidates = vocabulary_service.prepare_priority_word_save.call_args.args[0]
    assert [candidate.model_dump(exclude_none=True) for candidate in priority_candidates] == [
        {"word_phrase": "begripa", "source_form": "begriper", "context_phrase": "Jag begriper inte."}
    ]
    enrichment_payload = json.loads(mock_chat_model.enrichment_model.ainvoke.call_args.args[0][1].content)
    assert enrichment_payload["new_words"][0]["context_phrase"] == "Jag begriper inte."
    assert enrichment_payload["target_translation_language"] == "English"
    assert set(enrichment_payload) == {"new_words", "target_translation_language"}


@pytest.mark.anyio
async def test_word_keeper_saves_corrected_word_instead_of_student_misspelling(specialist, mock_chat_model, mock_user):
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="våren",
                translation="spring",
                example_phrase="Våren är min favoritårstid.",
                extra_info='noun; corrected from student form "varen"',
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(
            _priority_entry("våren", "missing", word_id=None, changed=False, source_form="varen")
        ),
        upsert_return={"action": "created", "word_id": 7, "changed": True},
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Jag gillar varen.",
                history=[],
                user=mock_user,
                teacher_response="There is no such word as 'varen'; use 'våren' for spring.",
                vocabulary_candidates=[WordSaveCandidate(word_phrase="våren", source_form="varen")],
                routing_reason="teacher emitted vocabulary_candidates",
            )
        )

    assert result.status == "action_taken"
    mock_chat_model.extraction_model.ainvoke.assert_not_awaited()
    assert result.artifacts["saved_words"] == ["våren"]
    priority_candidates = vocabulary_service.prepare_priority_word_save.call_args[0][0]
    assert [candidate.model_dump(exclude_none=True) for candidate in priority_candidates] == [
        {"word_phrase": "våren", "source_form": "varen"}
    ]

    enrichment_payload = json.loads(mock_chat_model.enrichment_model.ainvoke.call_args[0][0][1].content)
    assert enrichment_payload["new_words"][0]["word_phrase"] == "våren"
    assert enrichment_payload["new_words"][0]["source_form"] == "varen"

    assert vocabulary_service.insert_or_prioritize_words.call_args.kwargs == {"user_id": 12}

    items = vocabulary_service.insert_or_prioritize_words.call_args.args[0]
    assert [item.model_dump() for item in items] == [
        {
            "word_phrase": "våren",
            "translation": "spring",
            "example_phrase": "Våren är min favoritårstid.",
            "extra_info": 'noun; corrected from student form "varen"',
            "in_learn": True,
            "priority_learn": 9,
        }
    ]


@pytest.mark.anyio
async def test_word_keeper_mixed_existing_and_new_enriches_only_new_word(specialist, mock_chat_model, mock_user):
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="1",
                word_phrase="begripa",
                translation="understand",
                example_phrase="Jag begriper inte frågan.",
                extra_info='verb; infinitive: begripa; context form "begriper" is present tense',
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(
            _priority_entry("noggrann", "prioritized", word_id=2),
            _priority_entry("begripa", "missing", word_id=None, changed=False, source_form="begriper"),
        ),
        upsert_return={"action": "created", "word_id": 3, "changed": True},
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Jag begriper inte.",
                history=[],
                user=mock_user,
                teacher_response="Let's keep this new word in mind: begripa.",
                vocabulary_candidates=[
                    WordSaveCandidate(word_phrase="noggrann"),
                    WordSaveCandidate(word_phrase="begripa", source_form="begriper"),
                ],
                routing_reason="teacher emitted vocabulary_candidates",
            )
        )

    assert result.status == "action_taken"
    mock_chat_model.extraction_model.ainvoke.assert_not_awaited()
    assert result.artifacts["saved_words"] == ["noggrann", "begripa"]
    assert result.artifacts["action_counts"] == {
        "created": 1,
        "restored": 0,
        "prioritized": 1,
        "already_prioritized": 0,
    }
    enrichment_payload = mock_chat_model.enrichment_model.ainvoke.call_args[0][0][1].content
    assert '"candidate_id": "1"' in enrichment_payload
    assert '"word_phrase": "begripa"' in enrichment_payload
    assert '"source_form": "begriper"' in enrichment_payload
    assert '"word_phrase": "noggrann"' not in enrichment_payload


@pytest.mark.anyio
async def test_word_keeper_matches_enrichment_by_candidate_id(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[WordSaveCandidate(word_phrase="avgörande")],
    )
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="avgorande",
                translation="decisive",
                example_phrase="Det var ett avgörande beslut.",
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(_priority_entry("avgörande", "missing", word_id=None, changed=False)),
        upsert_return={"action": "created", "word_id": 3, "changed": True},
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save this word for me: avgörande",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "action_taken"
    vocabulary_service.insert_or_prioritize_words.assert_awaited_once()
    items = vocabulary_service.insert_or_prioritize_words.call_args.args[0]
    assert items[0].word_phrase == "avgörande"
    assert items[0].translation == "decisive"
    assert items[0].example_phrase == "Det var ett avgörande beslut."
    assert items[0].extra_info is None
    assert vocabulary_service.insert_or_prioritize_words.call_args.kwargs == {"user_id": 12}


@pytest.mark.anyio
async def test_word_keeper_skips_new_words_when_enrichment_fails(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[WordSaveCandidate(word_phrase="noggrann"), WordSaveCandidate(word_phrase="begripa")],
    )
    mock_chat_model.enrichment_model.ainvoke.side_effect = RuntimeError("llm exploded")
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(
            _priority_entry("noggrann", "prioritized", word_id=2),
            _priority_entry("begripa", "missing", word_id=None, changed=False),
        ),
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save these words.",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "action_taken"
    assert result.artifacts["saved_words"] == ["noggrann"]
    assert result.artifacts["skipped_words"] == [{"word_phrase": "begripa", "reason": "enrichment_failed"}]
    vocabulary_service.insert_or_prioritize_words.assert_not_awaited()


@pytest.mark.anyio
async def test_word_keeper_skips_new_word_with_incomplete_enrichment(specialist, mock_chat_model, mock_user):
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="förutsättning",
                translation=None,
                example_phrase="En viktig förutsättning är tid.",
            )
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(_priority_entry("förutsättning", "missing", word_id=None, changed=False)),
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
                teacher_response="These are good words to memorize: förutsättning.",
                vocabulary_candidates=[WordSaveCandidate(word_phrase="förutsättning")],
                routing_reason="teacher emitted vocabulary_candidates",
            )
        )

    assert result.status == "no_action"
    mock_chat_model.extraction_model.ainvoke.assert_not_awaited()
    assert result.artifacts["saved_words"] == []
    assert result.artifacts["skipped_words"] == [
        {"word_phrase": "förutsättning", "reason": "missing_required_fields_after_enrichment"}
    ]
    vocabulary_service.insert_or_prioritize_words.assert_not_awaited()


@pytest.mark.anyio
async def test_word_keeper_returns_no_action_when_extractor_finds_none(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    result = await specialist.run(SpecialistContext(message="Hello", history=[], user=mock_user, routing_reason="none"))

    assert result.status == "no_action"
    assert result.artifacts["saved_words"] == []
    mock_chat_model.enrichment_model.ainvoke.assert_not_awaited()


@pytest.mark.anyio
async def test_word_keeper_returns_error_on_priority_failure(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[WordSaveCandidate(word_phrase="avgörande")],
    )
    vocabulary_service = _mock_vocabulary_service()
    vocabulary_service.prepare_priority_word_save.side_effect = RuntimeError("db exploded")

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save this word for me: avgörande",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "error"
    assert result.actions[0].status == "error"


@pytest.mark.anyio
async def test_word_keeper_reports_batch_save_failure_when_new_word_insert_fails(
    specialist, mock_chat_model, mock_user
):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(
        decision="save_words",
        candidates=[WordSaveCandidate(word_phrase="avgörande"), WordSaveCandidate(word_phrase="noggrann")],
    )
    mock_chat_model.enrichment_model.ainvoke.return_value = WordKeeperEnrichment(
        items=[
            WordEnrichmentItem(
                candidate_id="0",
                word_phrase="avgörande",
                translation="decisive",
                example_phrase="Det var ett avgörande beslut.",
            ),
            WordEnrichmentItem(
                candidate_id="1",
                word_phrase="noggrann",
                translation="careful",
                example_phrase="Var noggrann med detaljerna.",
            ),
        ]
    )
    vocabulary_service = _mock_vocabulary_service(
        priority_actions=_priority_actions(
            _priority_entry("avgörande", "missing", word_id=None, changed=False),
            _priority_entry("noggrann", "missing", word_id=None, changed=False),
        ),
        upsert_side_effect=RuntimeError("db exploded"),
    )

    with patch(
        "runestone.agents.specialists.word_keeper.provide_vocabulary_service",
        _service_provider(vocabulary_service),
    ):
        result = await specialist.run(
            SpecialistContext(
                message="Save these words for me: avgörande, noggrann",
                history=[],
                user=mock_user,
                routing_reason="explicit save request",
            )
        )

    assert result.status == "error"
    assert result.actions[0].status == "error"
    assert result.artifacts["saved_words"] == []
    assert len(result.artifacts["skipped_words"]) == 2
    assert [item["word_phrase"] for item in result.artifacts["skipped_words"]] == ["avgörande", "noggrann"]
    assert all(item["reason"].startswith("vocabulary_service_error:") for item in result.artifacts["skipped_words"])
    vocabulary_service.repo.db.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_word_keeper_payload_uses_user_mother_tongue(specialist, mock_chat_model, mock_user):
    mock_user.mother_tongue = "Finnish"
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Save this word for me: avgörande",
            history=[],
            user=mock_user,
            routing_reason="explicit save request",
        )
    )

    call_args = mock_chat_model.extraction_model.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"target_translation_language": "Finnish"' in payload
    assert '"message": "Save this word for me: avgörande"' in payload
    assert '"teacher_response": null' in payload


@pytest.mark.anyio
async def test_word_keeper_payload_defaults_translation_language_to_english(specialist, mock_chat_model, mock_user):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Save this word for me: avgörande",
            history=[],
            user=mock_user,
            routing_reason="explicit save request",
        )
    )

    call_args = mock_chat_model.extraction_model.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"target_translation_language": "English"' in payload
    assert '"message": "Save this word for me: avgörande"' in payload
    assert '"teacher_response": null' in payload


@pytest.mark.anyio
async def test_word_keeper_extraction_payload_includes_teacher_response_for_deictic_save_request(
    specialist, mock_chat_model, mock_user
):
    mock_chat_model.extraction_model.ainvoke.return_value = WordKeeperExtraction(decision="no_action", candidates=[])

    await specialist.run(
        SpecialistContext(
            message="Save that word for me.",
            history=[],
            teacher_response="Begripa means understand.",
            user=mock_user,
            routing_reason="explicit save request",
        )
    )

    call_args = mock_chat_model.extraction_model.ainvoke.call_args[0][0]
    payload = call_args[1].content
    assert '"message": "Save that word for me."' in payload
    assert '"target_translation_language": "English"' in payload
    assert '"teacher_response": "Begripa means understand."' in payload
