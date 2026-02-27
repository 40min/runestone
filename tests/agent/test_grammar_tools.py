"""
Tests for grammar reference tools.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from runestone.agent.tools import grammar as grammar_tools
from runestone.services.grammar_service import GrammarService


@pytest.fixture
def mock_grammar_tools():
    """Create mock grammar tool runtime context."""
    index = MagicMock()
    # Use regular MagicMock for methods called via asyncio.to_thread (sync functions in thread pool)
    index.search = MagicMock()
    service = MagicMock()
    # Use regular MagicMock for methods called via asyncio.to_thread (sync functions in thread pool)
    service.get_cheatsheet_content = MagicMock()
    runtime = SimpleNamespace(context=SimpleNamespace(grammar_index=index, grammar_service=service))
    return runtime, index, service


@pytest.mark.anyio
async def test_search_grammar_tool(mock_grammar_tools):
    """Test search_grammar tool formatting using metadata path."""
    runtime, mock_index, _ = mock_grammar_tools
    mock_doc = Document(
        page_content="Adjective comparison",
        metadata={
            "url": "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation",
            "annotation": "Adjective comparison rules",
            "path": "adjectives/komparation.md",
        },
    )
    mock_index.search.return_value = [mock_doc]

    result_json = await grammar_tools.search_grammar.coroutine(query="comparison", top_k=1, runtime=runtime)
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Adjective comparison rules"
    assert result["results"][0]["path"] == "adjectives/komparation.md"
    assert result["results"][0]["url"] == "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation"


@pytest.mark.anyio
async def test_search_grammar_no_results(mock_grammar_tools):
    """Test search_grammar with no results."""
    runtime, mock_index, _ = mock_grammar_tools
    mock_index.search.return_value = []

    result_json = await grammar_tools.search_grammar.coroutine(query="nonexistent", top_k=3, runtime=runtime)
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert result["results"] == []


@pytest.mark.anyio
async def test_read_grammar_page_tool(mock_grammar_tools):
    """Test read_grammar_page tool."""
    runtime, _, mock_service = mock_grammar_tools
    mock_service.get_cheatsheet_content.return_value = "# Grammar Content"

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="verbs/present", runtime=runtime)
    assert result == "# Grammar Content"
    mock_service.get_cheatsheet_content.assert_called_once_with("verbs/present.md")


@pytest.mark.anyio
async def test_read_grammar_page_error(mock_grammar_tools):
    """Test read_grammar_page with error handling."""
    runtime, _, mock_service = mock_grammar_tools
    mock_service.get_cheatsheet_content.side_effect = FileNotFoundError("Not found")

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="invalid", runtime=runtime)
    assert "Error: Grammar page not found" in result


@pytest.fixture
def real_grammar_tools(tmp_path):
    """Create runtime context with a real GrammarService."""
    index = MagicMock()
    index.search = MagicMock()
    service = GrammarService(str(tmp_path))
    runtime = SimpleNamespace(context=SimpleNamespace(grammar_index=index, grammar_service=service))
    return runtime, tmp_path


@pytest.mark.anyio
async def test_read_grammar_page_success_real_service(real_grammar_tools):
    """Read markdown content via real GrammarService."""
    runtime, cheatsheets_dir = real_grammar_tools
    verbs_dir = cheatsheets_dir / "verbs"
    verbs_dir.mkdir()
    (verbs_dir / "presens.md").write_text("# Verb Presens\nContent here.", encoding="utf-8")

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="verbs/presens", runtime=runtime)
    assert "# Verb Presens" in result
    assert "Content here." in result


@pytest.mark.anyio
async def test_read_grammar_page_traversal_rejected_real_service(real_grammar_tools):
    """Ensure traversal attempts are rejected by GrammarService validation."""
    runtime, _ = real_grammar_tools

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="../config.py", runtime=runtime)
    assert "Error: Invalid cheatsheet path:" in result
    assert "Invalid file path" in result

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="/etc/passwd", runtime=runtime)
    assert "Error: Invalid cheatsheet path:" in result


@pytest.mark.anyio
async def test_read_grammar_page_not_found_real_service(real_grammar_tools):
    """Ensure missing cheatsheet is surfaced as 'not found'."""
    runtime, _ = real_grammar_tools

    result = await grammar_tools.read_grammar_page.coroutine(cheatsheet_path="nonexistent/page", runtime=runtime)
    assert "Error: Grammar page not found: nonexistent/page" in result
