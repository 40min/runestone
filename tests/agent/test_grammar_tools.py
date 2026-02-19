"""
Tests for grammar reference tools.
"""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from runestone.agent.tools.grammar import init_grammar_index, read_grammar_page, search_grammar


@pytest.fixture
def mock_index():
    """Create and initialize a mock GrammarIndex."""
    index = MagicMock()
    init_grammar_index(index)
    yield index
    # Reset singleton after test
    init_grammar_index(None)


def test_search_grammar_tool(mock_index):
    """Test search_grammar tool formatting and path extraction."""
    mock_doc = Document(
        page_content="Adjective comparison",
        metadata={
            "url": "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation",
            "annotation": "Adjective comparison rules",
        },
    )
    mock_index.search.return_value = [mock_doc]

    result_json = search_grammar.invoke({"query": "comparison", "top_k": 1})
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Adjective comparison rules"
    assert result["results"][0]["path"] == "adjectives/komparation"
    assert result["results"][0]["url"] == "http://localhost:5173/?view=grammar&cheatsheet=adjectives/komparation"


def test_search_grammar_no_results(mock_index):
    """Test search_grammar with no results."""
    mock_index.search.return_value = []
    result_json = search_grammar.invoke({"query": "nonexistent", "top_k": 5})
    result = json.loads(result_json)

    assert result["tool"] == "search_grammar"
    assert result["results"] == []


def test_read_grammar_page_tool(mock_index):
    """Test read_grammar_page tool."""
    mock_index.read_page.return_value = "# Grammar Content"

    result = read_grammar_page.invoke({"cheatsheet_path": "verbs/present"})
    assert result == "# Grammar Content"
    mock_index.read_page.assert_called_once_with("verbs/present")


def test_read_grammar_page_error(mock_index):
    """Test read_grammar_page with error handling."""
    mock_index.read_page.side_effect = FileNotFoundError("Not found")

    result = read_grammar_page.invoke({"cheatsheet_path": "invalid"})
    assert "Error: Grammar page not found" in result
