import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from runestone.agents.specialists.base import SpecialistContext
from runestone.agents.specialists.news_agent import NEWS_AGENT_SYSTEM_PROMPT, NewsAgentSpecialist


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.news_agent_provider = "openrouter"
    settings.news_agent_model = "test-model"
    return settings


@pytest.fixture
def specialist(mock_settings):
    with patch("runestone.agents.specialists.news_agent.build_chat_model", return_value=MagicMock()):
        with patch("runestone.agents.specialists.news_agent.create_agent"):
            specialist = NewsAgentSpecialist(mock_settings)
            specialist.agent = AsyncMock()
            return specialist


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 9
    user.mother_tongue = "English"
    return user


def test_news_agent_prompt_is_conservative():
    assert "Be conservative. If the topic is vague, return `no_action`." in NEWS_AGENT_SYSTEM_PROMPT
    assert "if it is, use the news tools to gather" in NEWS_AGENT_SYSTEM_PROMPT
    assert "Base your decision only on the latest student message" in NEWS_AGENT_SYSTEM_PROMPT
    assert "Use `search_news_with_dates` first when you do act." in NEWS_AGENT_SYSTEM_PROMPT
    assert "## Act when" in NEWS_AGENT_SYSTEM_PROMPT
    assert "## Return `no_action` when" in NEWS_AGENT_SYSTEM_PROMPT
    assert "Use `read_url` only for selected article URLs" in NEWS_AGENT_SYSTEM_PROMPT
    assert "max 5 search results and max 2 `read_url` calls" in NEWS_AGENT_SYSTEM_PROMPT
    assert "nyheter om Sverige" in NEWS_AGENT_SYSTEM_PROMPT
    assert "senaste nyheterna i Sverige" in NEWS_AGENT_SYSTEM_PROMPT
    assert "do not downgrade to" in NEWS_AGENT_SYSTEM_PROMPT


def test_news_agent_uses_news_agent_model_profile(mock_settings):
    with patch("runestone.agents.specialists.news_agent.build_chat_model", return_value=MagicMock()) as mock_build:
        with patch("runestone.agents.specialists.news_agent.create_agent"):
            NewsAgentSpecialist(mock_settings)
    mock_build.assert_called_once_with(mock_settings, "news_agent")


@pytest.mark.anyio
async def test_news_agent_returns_parsed_action_result(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"action_taken","actions":[{"tool":"search_news_with_dates","status":"success",'
                    '"summary":"Fetched 3 topical results"}],"info_for_teacher":"Prepared 3 sources.",'
                    '"artifacts":{"topic":"ekonomi","query":"svenska ekonominyheter","timelimit":"w",'
                    '"results":[{"title":"Ekonomi","url":"https://example.com/e1","date":"2026-04-06",'
                    '"snippet":"summary","article_text":""}],"sources":[{"title":"Ekonomi",'
                    '"url":"https://example.com/e1","date":"2026-04-06"}]}}'
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Show me Swedish news about economy",
            history=[],
            user=mock_user,
            routing_reason="known topic",
        )
    )

    assert result.status == "action_taken"
    assert result.actions[0].tool == "search_news_with_dates"
    assert result.artifacts["sources"][0]["url"] == "https://example.com/e1"


@pytest.mark.anyio
async def test_news_agent_returns_no_action_for_vague_request(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"topic":"","query":"","timelimit":"m","results":[],"sources":[]}}'
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Any news today?",
            history=[],
            user=mock_user,
            routing_reason="vague request",
        )
    )

    assert result.status == "no_action"
    assert result.artifacts["results"] == []


@pytest.mark.anyio
async def test_news_agent_payload_uses_current_student_message(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"topic":"","query":"","timelimit":"m","results":[],"sources":[]}}'
                )
            )
        ]
    }

    await specialist.run(
        SpecialistContext(
            message="Find Swedish news about sports",
            history=[],
            user=mock_user,
            routing_reason="known topic",
        )
    )

    args, kwargs = specialist.agent.ainvoke.call_args
    payload = json.loads(args[0]["messages"][0].content)
    assert payload["student_message"] == "Find Swedish news about sports"
    assert payload["phase"] == "pre_response"
    assert kwargs["context"].user == mock_user


@pytest.mark.anyio
async def test_news_agent_returns_error_when_agent_output_is_invalid(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {"messages": [AIMessage(content="not json")]}

    result = await specialist.run(
        SpecialistContext(
            message="News about energy",
            history=[],
            user=mock_user,
            routing_reason="known topic",
        )
    )

    assert result.status == "error"


@pytest.mark.anyio
async def test_news_agent_parses_fenced_json_output(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    "```json\n"
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"topic":"","query":"","timelimit":"m","results":[],"sources":[]}}'
                    "\n```"
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Any news?",
            history=[],
            user=mock_user,
            routing_reason="vague request",
        )
    )

    assert result.status == "no_action"


@pytest.mark.anyio
async def test_news_agent_parses_json_with_prefixed_text(specialist, mock_user):
    specialist.agent.ainvoke.return_value = {
        "messages": [
            AIMessage(
                content=(
                    "Here is the result:\n\n```json\n"
                    '{"status":"no_action","actions":[],"info_for_teacher":"",'
                    '"artifacts":{"topic":"","query":"","timelimit":"m","results":[],"sources":[]}}'
                    "\n```"
                )
            )
        ]
    }

    result = await specialist.run(
        SpecialistContext(
            message="Any news?",
            history=[],
            user=mock_user,
            routing_reason="vague request",
        )
    )

    assert result.status == "no_action"
