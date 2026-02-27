"""
Grammar search and reading tools for the teacher agent.
"""

import asyncio
import json
import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from runestone.agent.tools.context import AgentContext

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


@tool("search_grammar", args_schema=SearchGrammarInput)
async def search_grammar(
    query: str,
    runtime: ToolRuntime[AgentContext],
    top_k: int = 3,
) -> str:
    """
    Search for relevant Swedish grammar cheatsheet pages.

    Use this when the student asks about grammar topics like verb conjugation,
    adjective comparison, word order, etc or it is good moment to refer to it
    (after some error for example).

    Args:
        query: Search query describing the grammar topic
        top_k: Maximum number of results to return (1-3)

    Returns:
        JSON string with search results in the format:
        {"tool": "search_grammar", "results": [{"title": "...", "url": "...", "path": "..."}]}
    """
    if runtime is None:
        return json.dumps({"error": "Missing tool runtime context"})

    grammar_index = runtime.context.grammar_index
    if grammar_index is None:
        return json.dumps({"error": "Grammar index not initialized"})

    try:
        # Run synchronous search in thread pool to avoid blocking
        results = await asyncio.to_thread(grammar_index.search, query, top_k=top_k)
        if not results:
            return json.dumps({"tool": "search_grammar", "results": []})

        formatted_results = []
        for doc in results:
            formatted_results.append(
                {
                    "title": doc.metadata.get("annotation", ""),
                    "url": doc.metadata.get("url", ""),
                    "path": doc.metadata.get("path", ""),
                }
            )

        return json.dumps({"tool": "search_grammar", "results": formatted_results})
    except Exception as e:
        logger.exception("Error searching grammar: %s", e)
        return json.dumps({"error": f"Grammar search failed: {str(e)}"})


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
