"""
Grammar search index using hybrid BM25 + FAISS retrieval.
"""

import logging
import threading
from pathlib import Path

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from runestone.config import settings
from runestone.rag.loader import load_grammar_documents

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class GrammarIndex:
    """
    Hybrid search index for grammar cheatsheets using BM25 (keywords) + FAISS (vectors).
    """

    def __init__(self, cheatsheets_dir: str, frontend_url: str):
        """
        Initialize grammar search index.

        Args:
            cheatsheets_dir: Directory containing cheatsheets and index.json
            frontend_url: Base URL to resolve {HOST} placeholders in URLs
        """
        self.cheatsheets_dir = cheatsheets_dir
        self.frontend_url = frontend_url.rstrip("/")
        self._initialized = False
        self._init_lock = threading.Lock()

    def _initialize(self):
        """Perform delayed loading of index to avoid app startup delay."""
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

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
            embeddings = self._load_embeddings()
            self.vector_store = FAISS.from_documents(vector_docs, embeddings)
            self.vector_retriever = self.vector_store.as_retriever(search_kwargs={"k": 10})

            # Combine with EnsembleRetriever
            logger.info("Creating ensemble retriever (BM25 + FAISS)")
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, self.vector_retriever], weights=[0.5, 0.5]
            )

            self._initialized = True
            logger.info("Grammar index initialized successfully")

    def _load_embeddings(self) -> HuggingFaceEmbeddings:
        """Load HuggingFaceEmbeddings model, attempting local cache first."""
        Path(settings.hf_cache_dir).mkdir(parents=True, exist_ok=True)

        # First try loading from cache only, avoiding any online HEAD requests
        try:
            model_kwargs = {"local_files_only": True}
            if settings.hf_token:
                model_kwargs["token"] = settings.hf_token
            return HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                cache_folder=settings.hf_cache_dir,
                model_kwargs=model_kwargs,
            )
        except Exception as e:
            logger.info(
                "Local model not found or failed to load (%s: %s). Downloading from Hugging Face...",
                type(e).__name__,
                e,
            )
            model_kwargs = {"local_files_only": False}
            if settings.hf_token:
                model_kwargs["token"] = settings.hf_token
            return HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                cache_folder=settings.hf_cache_dir,
                model_kwargs=model_kwargs,
            )

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

        self._initialize()

        results = self.ensemble_retriever.invoke(query)

        # Deduplicate by URL and limit to top_k
        seen_urls = set()
        unique_results: list[Document] = []
        for doc in results:
            url = doc.metadata.get("url", "")
            if url and url not in seen_urls:
                # Resolve {HOST} placeholder
                resolved_url = url.replace("{HOST}", self.frontend_url)
                doc.metadata["url"] = resolved_url
                unique_results.append(doc)
                seen_urls.add(url)
                if len(unique_results) >= top_k:
                    break

        logger.info("Search query='%s' returned %d results", query, len(unique_results))
        return unique_results
