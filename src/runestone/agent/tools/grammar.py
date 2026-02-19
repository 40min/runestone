"""
Grammar search and reading tools for the teacher agent.
"""

import json
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from runestone.rag.index import GrammarIndex
from runestone.services.grammar_service import GrammarService

logger = logging.getLogger(__name__)

# Module-level singleton reference
_grammar_index: GrammarIndex | None = None
_grammar_service: GrammarService | None = None


def init_grammar_index(index: GrammarIndex | None, grammar_service: GrammarService | None = None) -> None:
    """
    Initialize the module-level grammar index singleton.

    Args:
        index: GrammarIndex instance created at app startup
        grammar_service: GrammarService instance created at app startup
    """
    global _grammar_index, _grammar_service
    _grammar_index = index
    _grammar_service = grammar_service
    logger.info("Grammar index initialized for agent tools")


class SearchGrammarInput(BaseModel):
    """Input for search_grammar tool."""

    query: str = Field(description="Search query for grammar topics (e.g., 'adjective comparison', 'past tense')")
    top_k: int = Field(default=5, description="Maximum number of results to return", ge=1, le=10)


class ReadGrammarPageInput(BaseModel):
    """Input for read_grammar_page tool."""

    cheatsheet_path: str = Field(
        description="Relative path to cheatsheet from search results (e.g., 'adjectives/adjectiv-komparation')"
    )


@tool("search_grammar", args_schema=SearchGrammarInput)
def search_grammar(query: str, top_k: int = 5) -> str:
    """
    Search for relevant Swedish grammar cheatsheet pages.

    Use this when the student asks about grammar topics like verb conjugation,
    adjective comparison, word order, etc or it is good moment to refer to it
    (after some error for example).

    Args:
        query: Search query describing the grammar topic
        top_k: Maximum number of results to return (1-10)

    Returns:
        JSON string with search results in the format:
        {"tool": "search_grammar", "results": [{"title": "...", "url": "...", "path": "..."}]}
    """
    if _grammar_index is None:
        return json.dumps({"error": "Grammar index not initialized"})

    try:
        results = _grammar_index.search(query, top_k=top_k)

        if not results:
            return json.dumps({"tool": "search_grammar", "results": []})

        formatted_results = []
        for doc in results:
            url = doc.metadata.get("url", "")
            annotation = doc.metadata.get("annotation", "")

            # Extract cheatsheet path from URL for read_grammar_page
            # URL format: {HOST}/?view=grammar&cheatsheet=adjectives%2Fadjectiv-komparation
            cheatsheet_path = ""
            if "cheatsheet=" in url:
                import urllib.parse

                params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if "cheatsheet" in params:
                    cheatsheet_path = urllib.parse.unquote(params["cheatsheet"][0])

            formatted_results.append({"title": annotation, "url": url, "path": cheatsheet_path})

        return json.dumps({"tool": "search_grammar", "results": formatted_results})

    except Exception as e:
        logger.exception("Error searching grammar: %s", e)
        return json.dumps({"error": f"Grammar search failed: {str(e)}"})


@tool("read_grammar_page", args_schema=ReadGrammarPageInput)
def read_grammar_page(cheatsheet_path: str) -> str:
    """
    Read the full content of a specific grammar cheatsheet page.

    Use this after search_grammar to get detailed grammar explanations.
    The cheatsheet_path comes from the 'path' field in search results.

    Args:
        cheatsheet_path: Relative path to cheatsheet (e.g., 'adjectives/adjectiv-komparation')

    Returns:
        Markdown content of the cheatsheet or error message
    """
    if _grammar_service is None:
        return "Error: Grammar index not initialized"

    try:
        filepath = cheatsheet_path if cheatsheet_path.endswith(".md") else f"{cheatsheet_path}.md"
        content = _grammar_service.get_cheatsheet_content(filepath)
        return content
    except FileNotFoundError:
        return f"Error: Grammar page not found: {cheatsheet_path}"
    except ValueError as e:
        return f"Error: Invalid cheatsheet path: {str(e)}"
    except Exception as e:
        logger.exception("Error reading grammar page: %s", e)
        return f"Error reading grammar page: {str(e)}"
