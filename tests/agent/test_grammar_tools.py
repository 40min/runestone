"""
Tests for grammar reference tools.
"""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from runestone.agent.tools.grammar import init_grammar_index, read_grammar_page, search_grammar
from runestone.services.grammar_service import GrammarService


@pytest.fixture
def mock_grammar_tools():
    """Create and initialize mock grammar tool singletons."""
    index = MagicMock()
    service = MagicMock()
    init_grammar_index(index, service)
    yield index, service
    # Reset singletons after test
    init_grammar_index(None, None)


def test_search_grammar_tool(mock_grammar_tools):
    """Test search_grammar tool formatting using metadata path."""
    mock_index, _ = mock_grammar_tools
    mock_doc = Document(
        page_content="Adjective comparison",
        metadata={
            "url": "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation",
            "annotation": "Adjective comparison rules",
            "path": "adjectives/komparation.md",
        },
    )
    mock_index.search.return_value = [mock_doc]

    result_json = search_grammar.invoke({"query": "comparison", "top_k": 1})
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Adjective comparison rules"
    assert result["results"][0]["path"] == "adjectives/komparation.md"
    assert result["results"][0]["url"] == "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation"


def test_search_grammar_no_results(mock_grammar_tools):
    """Test search_grammar with no results."""
    mock_index, _ = mock_grammar_tools
    mock_index.search.return_value = []
    result_json = search_grammar.invoke({"query": "nonexistent", "top_k": 5})
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert result["results"] == []


def test_read_grammar_page_tool(mock_grammar_tools):
    """Test read_grammar_page tool."""
    _, mock_service = mock_grammar_tools
    mock_service.get_cheatsheet_content.return_value = "# Grammar Content"

    result = read_grammar_page.invoke({"cheatsheet_path": "verbs/present"})
    assert result == "# Grammar Content"
    mock_service.get_cheatsheet_content.assert_called_once_with("verbs/present.md")


def test_read_grammar_page_error(mock_grammar_tools):
    """Test read_grammar_page with error handling."""
    _, mock_service = mock_grammar_tools
    mock_service.get_cheatsheet_content.side_effect = FileNotFoundError("Not found")

    result = read_grammar_page.invoke({"cheatsheet_path": "invalid"})
    assert "Error: Grammar page not found" in result


@pytest.fixture
def real_grammar_tools(tmp_path):
    """Initialize grammar tool singletons with a real GrammarService."""
    index = MagicMock()
    service = GrammarService(str(tmp_path))
    init_grammar_index(index, service)
    yield tmp_path
    init_grammar_index(None, None)


def test_read_grammar_page_success_real_service(real_grammar_tools):
    """Read markdown content via real GrammarService."""
    cheatsheets_dir = real_grammar_tools
    verbs_dir = cheatsheets_dir / "verbs"
    verbs_dir.mkdir()
    (verbs_dir / "presens.md").write_text("# Verb Presens\nContent here.", encoding="utf-8")

    result = read_grammar_page.invoke({"cheatsheet_path": "verbs/presens"})
    assert "# Verb Presens" in result
    assert "Content here." in result


def test_read_grammar_page_traversal_rejected_real_service(real_grammar_tools):
    """Ensure traversal attempts are rejected by GrammarService validation."""
    result = read_grammar_page.invoke({"cheatsheet_path": "../config.py"})
    assert "Error: Invalid cheatsheet path:" in result
    assert "Invalid file path" in result

    result = read_grammar_page.invoke({"cheatsheet_path": "/etc/passwd"})
    assert "Error: Invalid cheatsheet path:" in result


def test_read_grammar_page_not_found_real_service(real_grammar_tools):
    """Ensure missing cheatsheet is surfaced as 'not found'."""
    result = read_grammar_page.invoke({"cheatsheet_path": "nonexistent/page"})
    assert "Error: Grammar page not found: nonexistent/page" in result
