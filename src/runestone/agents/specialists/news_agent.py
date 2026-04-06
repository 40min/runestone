"""
Pre-response specialist that handles topical news retrieval with agent-owned tools.
"""

import json
import logging
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from runestone.agents.llm import build_chat_model
from runestone.agents.specialists.base import BaseSpecialist, SpecialistContext, SpecialistResult
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.news import search_news_with_dates
from runestone.agents.tools.read_url import read_url
from runestone.config import Settings

logger = logging.getLogger(__name__)

NEWS_AGENT_SYSTEM_PROMPT = """
You are NewsAgent, an internal specialist for a Swedish tutoring app.
You do not talk to the student. Your job is to decide whether the current student turn
is specific enough for topical news retrieval and, if it is, use the news tools to gather
bounded context for the teacher.

## Core Rules
- Be conservative. If the topic is vague, return `no_action`.
- Base your decision only on the latest student message in this turn.
- Use `search_news_with_dates` first when you do act.
- Use `read_url` only for selected article URLs when snippets are too thin to help the teacher.
- Never use `read_url` as a general web crawler.
- Keep retrieval bounded: max 5 search results and max 2 `read_url` calls.

## Act when
- The student clearly names a topic or domain for news.
- The student asks to read, discuss, or summarize news about that topic.
- The student asks about current weather for a specific city or region.
- The student asks any other specific real-time factual question (e.g. what happened in an election, current events).

## Return `no_action` when
- The student asks for generic news with no topic.
- The student asks about an arbitrary page URL instead of topic news retrieval.
- The request is grammar-only or general factual tutoring without a real-time search intent.

## Search guidance
- For weather queries, search for current weather conditions in the named location (e.g. "väder Helsinki imorgon").
- For news topics, search in the appropriate language; prefer Swedish for Swedish-language context.
- Keep retrieval bounded: max 5 search results and max 2 `read_url` calls.

## Output Contract
Return valid JSON with this exact shape and no extra text:
{
  "status": "no_action" | "action_taken" | "error",
  "actions": [{"tool": string, "status": "success" | "error", "summary": string}],
  "info_for_teacher": string,
  "artifacts": {
    "topic": string,
    "query": string,
    "timelimit": "d" | "w" | "m" | "y",
    "results": [
      {
        "title": string,
        "url": string,
        "date": string,
        "snippet": string,
        "article_text": string
      }
    ],
    "sources": [{"title": string, "url": string, "date": string}]
  }
}

If no action is needed, return an empty `results` and `sources` list.
"""


class NewsAgentSpecialist(BaseSpecialist):
    """Tool-using pre-response specialist for topic-based news retrieval."""

    def __init__(self, settings: Settings):
        super().__init__(name="news_agent")
        self.settings = settings
        self.model = build_chat_model(settings, "news_agent")
        self.agent = self._build_agent()
        logger.info(
            "[agents:news] Initialized NewsAgentSpecialist with provider=%s, model=%s",
            settings.news_agent_provider,
            settings.news_agent_model,
        )

    def _build_agent(self):
        """Build the internal tool-using agent for conservative news retrieval."""
        return create_agent(
            model=self.model,
            tools=[search_news_with_dates, read_url],
            system_prompt=NEWS_AGENT_SYSTEM_PROMPT,
            context_schema=AgentContext,
        )

    async def run(self, context: SpecialistContext) -> SpecialistResult:
        payload = {
            "student_message": context.message,
            "history": [msg.model_dump(mode="json") for msg in context.history],
            "routing_reason": context.routing_reason,
            "phase": "pre_response",
        }

        try:
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=json.dumps(payload, ensure_ascii=False))]},
                context=AgentContext(user=context.user),
            )
        except Exception as exc:
            logger.warning("[agents:news] Agent execution failed: %s", exc, exc_info=True)
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"topic": "", "query": "", "timelimit": "m", "results": [], "sources": []},
            )

        parsed = self._parse_result(result.get("messages", []))
        if parsed is None:
            logger.warning("[agents:news] Failed to parse final agent result")
            return SpecialistResult(
                status="error",
                actions=[],
                info_for_teacher="",
                artifacts={"topic": "", "query": "", "timelimit": "m", "results": [], "sources": []},
            )
        return parsed

    @staticmethod
    def _parse_result(messages: list[Any]) -> SpecialistResult | None:
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            if getattr(message, "tool_calls", None):
                continue
            content = message.content
            if not isinstance(content, str) or not content.strip():
                continue
            json_content = content.strip()
            start = json_content.find("{")
            end = json_content.rfind("}")
            if start != -1 and end != -1 and end >= start:
                json_content = json_content[start : end + 1]
            try:
                return SpecialistResult.model_validate_json(json_content)
            except (ValidationError, ValueError):
                continue
        return None
