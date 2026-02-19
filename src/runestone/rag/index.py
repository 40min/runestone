"""
Grammar search index using hybrid BM25 + FAISS retrieval.
"""

import logging
from pathlib import Path

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from runestone.rag.loader import load_grammar_documents

logger = logging.getLogger(__name__)


class GrammarIndex:
    """
    Hybrid search index for grammar cheatsheets using BM25 (keywords) + FAISS (vectors).
    """

    def __init__(self, cheatsheets_dir: str, app_base_url: str):
        """
        Initialize grammar search index.

        Args:
            cheatsheets_dir: Directory containing cheatsheets and index.json
            app_base_url: Base URL to resolve {HOST} placeholders in URLs

        Raises:
            FileNotFoundError: If index.json doesn't exist
            ValueError: If index.json is malformed
        """
        self.cheatsheets_dir = cheatsheets_dir
        self.app_base_url = app_base_url.rstrip("/")

        index_path = str(Path(self.cheatsheets_dir) / "index.json")
        logger.info("Loading grammar documents from %s", index_path)

        keyword_docs, vector_docs = load_grammar_documents(index_path)

        if not keyword_docs or not vector_docs:
            raise ValueError(f"No valid documents found in {index_path}")

        # Build BM25 retriever from keyword docs (tags)
        logger.info("Building BM25 retriever from %d keyword documents", len(keyword_docs))
        self.bm25_retriever = BM25Retriever.from_documents(keyword_docs)
        self.bm25_retriever.k = 10  # Retrieve more candidates for ensemble

        # Build FAISS vector store from vector docs (annotations)
        logger.info("Building FAISS index from %d vector documents (this may take a minute...)", len(vector_docs))
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self.vector_store = FAISS.from_documents(vector_docs, embeddings)
        self.vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": 10})

        # Combine with EnsembleRetriever
        logger.info("Creating ensemble retriever (BM25 + FAISS)")
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.vector_retriever], weights=[0.5, 0.5]
        )

        logger.info("Grammar index initialized successfully")

    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """
        Search for relevant grammar pages.

        Args:
            query: Search query
            top_k: Maximum number of results to return

        Returns:
            List of Document objects with metadata (url, annotation, tags)
        """
        if not query.strip():
            return []

        results = self.ensemble_retriever.invoke(query)

        # Deduplicate by URL and limit to top_k
        seen_urls = set()
        unique_results = []
        for doc in results:
            url = doc.metadata.get("url", "")
            if url and url not in seen_urls:
                # Resolve {HOST} placeholder
                resolved_url = url.replace("{HOST}", self.app_base_url)
                doc.metadata["url"] = resolved_url
                unique_results.append(doc)
                seen_urls.add(url)
                if len(unique_results) >= top_k:
                    break

        logger.info("Search query='%s' returned %d results", query, len(unique_results))
        return unique_results
