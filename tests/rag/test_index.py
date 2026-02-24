"""
Tests for GrammarIndex hybrid search.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from runestone.rag.index import GrammarIndex


@pytest.fixture
def mock_grammar_files(tmp_path):
    """Create mock index.json and cheatsheets."""
    index_data = [
        {
            "url": "{HOST}/?view=grammar&cheatsheet=verbs/presens",
            "tags": ["verb", "presens"],
            "annotation": "Verb present tense",
        },
        {
            "url": "{HOST}/?view=grammar&cheatsheet=nouns/plurals",
            "tags": ["noun", "plural"],
            "annotation": "Noun plurals",
        },
    ]
    index_file = tmp_path / "index.json"
    index_file.write_text(json.dumps(index_data), encoding="utf-8")
    return tmp_path


@pytest.fixture
def mock_embeddings():
    """Mock HuggingFaceEmbeddings to avoid loading models."""
    with patch("runestone.rag.index.HuggingFaceEmbeddings") as mock_class:
        mock_instance = MagicMock()
        # Mock embed_documents to return dummy vectors of size 128
        mock_instance.embed_documents.side_effect = lambda texts: [[0.1] * 128 for _ in texts]
        mock_instance.embed_query.return_value = [0.1] * 128
        mock_class.return_value = mock_instance
        yield mock_instance


def test_grammar_index_init(mock_grammar_files, mock_embeddings):
    """Test initialization of GrammarIndex."""
    index = GrammarIndex(str(mock_grammar_files), "http://test-host:5173")

    # Initialize because it's lazy loaded
    index._initialize()

    assert index.frontend_url == "http://test-host:5173"
    assert index.bm25_retriever is not None
    assert index.vector_store is not None
    assert index.ensemble_retriever is not None


def test_grammar_index_search(mock_grammar_files, mock_embeddings):
    """Test hybrid search and {HOST} resolution."""
    index = GrammarIndex(str(mock_grammar_files), "http://test-host")

    # Mock the ensemble retriever's invoke method
    mock_doc = Document(
        page_content="Verb present tense",
        metadata={
            "url": "{HOST}/?view=grammar&cheatsheet=verbs/presens",
            "annotation": "Verb present tense",
        },
    )

    # Use class-level patch because instance patching can fail on Pydantic/complex inherited methods
    with patch("langchain_classic.retrievers.ensemble.EnsembleRetriever.invoke", return_value=[mock_doc]):
        results = index.search("presens", top_k=5)

        assert len(results) == 1
        assert results[0].metadata["url"] == "http://test-host/?view=grammar&cheatsheet=verbs/presens"
        assert results[0].metadata["annotation"] == "Verb present tense"


def test_grammar_index_search_empty(mock_grammar_files, mock_embeddings):
    """Test search with empty query."""
    index = GrammarIndex(str(mock_grammar_files), "http://test-host")
    results = index.search("  ")
    assert results == []
