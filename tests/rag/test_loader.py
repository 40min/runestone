"""
Tests for grammar document loader.
"""

import json

import pytest

from runestone.rag.loader import load_grammar_documents, read_cheatsheet_content


@pytest.fixture
def mock_grammar_data(tmp_path):
    """Create a temporary grammar index and cheatsheets."""
    index_data = [
        {
            "url": "http://localhost:5173/?view=grammar&cheatsheet=verbs/presens",
            "tags": ["verb", "presens"],
            "annotation": "How to conjugate verbs in present tense",
        },
        {
            "url": "http://localhost:5173/?view=grammar&cheatsheet=nouns/plurall",
            "tags": ["noun", "plural"],
            "annotation": "Noun plural endings",
        },
    ]

    index_file = tmp_path / "index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f)

    # Create dummy cheatsheet files
    verbs_dir = tmp_path / "verbs"
    verbs_dir.mkdir()
    (verbs_dir / "presens.md").write_text("# Verb Presens\nContent here.", encoding="utf-8")

    return tmp_path


def test_load_grammar_documents(mock_grammar_data):
    """Test loading documents from index.json."""
    index_path = str(mock_grammar_data / "index.json")
    keyword_docs, vector_docs = load_grammar_documents(index_path)

    assert len(keyword_docs) == 2
    assert len(vector_docs) == 2

    # Check keyword doc (tags as content)
    assert keyword_docs[0].page_content == "verb presens"
    assert keyword_docs[0].metadata["url"] == "http://localhost:5173/?view=grammar&cheatsheet=verbs/presens"

    # Check vector doc (annotation as content)
    assert vector_docs[1].page_content == "Noun plural endings"
    assert vector_docs[1].metadata["tags"] == ["noun", "plural"]


def test_load_grammar_documents_not_found():
    """Test error when index.json is missing."""
    with pytest.raises(FileNotFoundError):
        load_grammar_documents("/non/existent/path/index.json")


def test_read_cheatsheet_content(mock_grammar_data):
    """Test reading cheatsheet markdown content."""
    content = read_cheatsheet_content(str(mock_grammar_data), "verbs/presens")
    assert "# Verb Presens" in content
    assert "Content here." in content


def test_read_cheatsheet_content_traversal(mock_grammar_data):
    """Test protection against path traversal."""
    with pytest.raises(ValueError, match="path traversal detected"):
        read_cheatsheet_content(str(mock_grammar_data), "../config.py")

    with pytest.raises(ValueError, match="path traversal detected"):
        read_cheatsheet_content(str(mock_grammar_data), "/etc/passwd")


def test_read_cheatsheet_content_not_found(mock_grammar_data):
    """Test error when cheatsheet file is missing."""
    with pytest.raises(FileNotFoundError):
        read_cheatsheet_content(str(mock_grammar_data), "nonexistent/page")
