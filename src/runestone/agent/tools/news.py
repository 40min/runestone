"""News search tool."""

import asyncio
import logging
from typing import Literal
from urllib.parse import urlparse

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

NewsTimeLimit = Literal["d", "w", "m", "y"]


def _is_swedish_source(url: str) -> bool:
    if not url:
        return False
    try:
        netloc = urlparse(url).netloc.split(":")[0].lower()
    except ValueError:
        return False
    return netloc.endswith(".se")


class NewsResult(BaseModel):
    """Single news result returned by the search tool."""

    title: str
    snippet: str
    url: str
    date: str


class NewsResultsOutput(BaseModel):
    """Structured output for news search results."""

    tool: str = Field("search_news_with_dates", description="Tool name for traceability")
    query: str
    timelimit: NewsTimeLimit
    region: str
    swedish_only: bool
    results: list[NewsResult]


MAX_NEWS_TO_FETCH = 10
DDGS_TIMEOUT = 20
DDGS_MAX_RETRIES = 2
DDGS_RETRY_DELAYS = (0.3, 0.6)


def _fetch_news_sync(
    query: str,
    k: int,
    timelimit: NewsTimeLimit,
    region: str,
) -> list[dict]:
    with DDGS(timeout=DDGS_TIMEOUT) as ddgs:
        return list(
            ddgs.news(
                query,
                max_results=k,
                timelimit=timelimit,
                region=region,
            )
            or []
        )


@tool("search_news_with_dates")
async def search_news_with_dates(
    query: str,
    k: int = MAX_NEWS_TO_FETCH,
    timelimit: NewsTimeLimit = "m",
    region: str = "se-sv",
    swedish_only: bool = False,
) -> dict:
    """
    Search Swedish-language news for a topic within a given time window.

    Args:
        query: Search query in Swedish (recommended) or English
        k: Max number of results to return
        timelimit: "d" (day), "w" (week), "m" (month), "y" (year)
        region: DuckDuckGo region code for localization (default: Swedish)
        swedish_only: If True, only return sources with a .se domain

    Returns:
        A structured dictionary containing the search results.
    """
    k = max(1, min(k, MAX_NEWS_TO_FETCH))
    results: list[NewsResult] = []
    ddgs_results = None

    for attempt in range(DDGS_MAX_RETRIES + 1):
        try:
            ddgs_results = await asyncio.to_thread(_fetch_news_sync, query, k, timelimit, region)
            break
        except RatelimitException as e:
            if attempt >= DDGS_MAX_RETRIES:
                logger.warning("News search rate limited for query='%s': %s", query, e)
                return {
                    "error": "News search is temporarily rate limited. Please try again in a minute.",
                    "error_type": "rate_limited",
                }
            delay = DDGS_RETRY_DELAYS[min(attempt, len(DDGS_RETRY_DELAYS) - 1)]
            await asyncio.sleep(delay)
        except DuckDuckGoSearchException as e:
            logger.exception("News search failed for query='%s'", query)
            return {"error": f"Error searching news: {str(e)}"}

    try:
        if ddgs_results is None:
            return {"error": "Error searching news: No results returned."}

        for item in ddgs_results:
            title = item.get("title") or "Untitled"
            snippet = item.get("body") or ""
            url = item.get("url") or ""
            date = item.get("date") or "unknown"

            if swedish_only and not _is_swedish_source(url):
                continue

            results.append(
                NewsResult(
                    title=title,
                    snippet=snippet,
                    url=url,
                    date=date,
                )
            )

        if not results:
            payload = NewsResultsOutput(
                query=query,
                timelimit=timelimit,
                region=region,
                swedish_only=swedish_only,
                results=[],
            )
            return payload.model_dump()

        payload = NewsResultsOutput(
            query=query,
            timelimit=timelimit,
            region=region,
            swedish_only=swedish_only,
            results=results,
        )
        return payload.model_dump()
    except DuckDuckGoSearchException as e:
        logger.exception("News search failed for query='%s'", query)
        return {"error": f"Error searching news: {str(e)}"}
