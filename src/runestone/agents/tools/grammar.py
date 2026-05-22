"""
Grammar search and reading tools for the teacher agent.
"""

import asyncio
import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from runestone.agents.tools.context import AgentContext

logger = logging.getLogger(__name__)


class SearchGrammarInput(BaseModel):
    """Input for search_grammar tool."""

    query: str = Field(description="Search query for grammar topics (e.g., 'adjective comparison', 'past tense')")
    top_k: int = Field(default=3, description="Maximum number of results to return", ge=1, le=3)


class ReadGrammarPageInput(BaseModel):
    """Input for read_grammar_page tool."""

    cheatsheet_path: str = Field(
        description="Relative path to cheatsheet from search results (e.g., 'adjectives/adjectiv-komparation')"
    )


class GrammarSearchResult(BaseModel):
    """Single grammar search result returned to the teacher agent."""

    title: str = Field(description="Human-readable grammar page title")
    url: str = Field(description="Public grammar page URL")
    path: str = Field(description="Internal cheatsheet path for read_grammar_page")


class GrammarSearchOutput(BaseModel):
    """Structured payload for grammar search results."""

    tool: str = Field("search_grammar", description="Tool name for traceability")
    results: list[GrammarSearchResult] = Field(description="Ordered grammar search matches")
    note: str | None = Field(default=None, description="Optional guidance when no useful matches were found")


@tool("search_grammar", args_schema=SearchGrammarInput)
async def search_grammar(
    query: str,
    runtime: ToolRuntime[AgentContext],
    top_k: int = 3,
) -> dict:
    """
    Search for relevant Swedish grammar cheatsheet pages.

    Use this when the student asks about grammar topics like verb conjugation,
    adjective comparison, word order, etc or it is good moment to refer to it
    (after some error for example).

    Args:
        query: Search query describing the grammar topic
        top_k: Maximum number of results to return (1-3)

    Returns:
        Structured search results in the format:
        {"tool": "search_grammar", "results": [{"title": "...", "url": "...", "path": "..."}]}
    """
    if runtime is None:
        return {"error": "Missing tool runtime context"}

    grammar_index = runtime.context.grammar_index
    if grammar_index is None:
        return {"error": "Grammar index not initialized"}

    try:
        # Run synchronous search in thread pool to avoid blocking
        results = await asyncio.to_thread(grammar_index.search, query, top_k=top_k)
        if not results:
            payload = GrammarSearchOutput(
                results=[],
                note="No matching grammar pages found. Respond without grammar links.",
            )
            return payload.model_dump()

        formatted_results: list[GrammarSearchResult] = []
        for doc in results:
            formatted_results.append(
                GrammarSearchResult(
                    title=doc.metadata.get("annotation", ""),
                    url=doc.metadata.get("url", ""),
                    path=doc.metadata.get("path", ""),
                )
            )

        payload = GrammarSearchOutput(results=formatted_results)
        return payload.model_dump()
    except Exception as e:
        logger.exception("Error searching grammar: %s", e)
        return {"error": f"Grammar search failed: {str(e)}"}


@tool("read_grammar_page", args_schema=ReadGrammarPageInput)
async def read_grammar_page(
    cheatsheet_path: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Read the full content of a specific grammar cheatsheet page.

    Use this after search_grammar to get detailed grammar explanations.
    The cheatsheet_path comes from the 'path' field in search results.

    Args:
        cheatsheet_path: Relative path to cheatsheet (e.g., 'adjectives/adjectiv-komparation')

    Returns:
        Markdown content of the cheatsheet or error message
    """
    logger.info("Reading grammar page: %s", cheatsheet_path)
    if runtime is None:
        return "Error: Missing tool runtime context"

    grammar_service = runtime.context.grammar_service
    if grammar_service is None:
        return "Error: Grammar service not initialized"

    try:
        filepath = cheatsheet_path if cheatsheet_path.endswith(".md") else f"{cheatsheet_path}.md"
        # Run synchronous file I/O in thread pool to avoid blocking
        return await asyncio.to_thread(grammar_service.get_cheatsheet_content, filepath)
    except FileNotFoundError:
        return f"Error: Grammar page not found: {cheatsheet_path}"
    except ValueError as e:
        return f"Error: Invalid cheatsheet path: {str(e)}"
    except Exception as e:
        logger.exception("Error reading grammar page: %s", e)
        return f"Error reading grammar page: {str(e)}"
