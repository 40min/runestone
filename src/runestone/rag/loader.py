"""
Grammar document loading and cheatsheet content reading.
"""

import json
import logging
from pathlib import Path

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_grammar_documents(index_path: str) -> tuple[list[Document], list[Document]]:
    """
    Load grammar documents from index.json for RAG indexing.

    Args:
        index_path: Path to cheatsheets/index.json

    Returns:
        Tuple of (keyword_docs, vector_docs):
        - keyword_docs: Documents with tags as content (for BM25)
        - vector_docs: Documents with annotations as content (for FAISS)

    Raises:
        FileNotFoundError: If index.json doesn't exist
        json.JSONDecodeError: If index.json is malformed
    """
    index_file = Path(index_path)
    if not index_file.exists():
        raise FileNotFoundError(f"Grammar index not found: {index_path}")

    with open(index_file, encoding="utf-8") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        raise ValueError(f"Expected list in {index_path}, got {type(entries)}")

    keyword_docs = []
    vector_docs = []

    for entry in entries:
        if not isinstance(entry, dict):
            logger.warning("Skipping non-dict entry in index: %s", entry)
            continue

        url = entry.get("url", "")
        tags = entry.get("tags", [])
        annotation = entry.get("annotation", "")

        if not url or not annotation:
            logger.warning("Skipping entry with missing url or annotation: %s", entry)
            continue

        metadata = {"url": url, "annotation": annotation, "tags": tags}

        # Keyword document: tags as content
        keyword_content = " ".join(tags) if tags else ""
        if keyword_content:
            keyword_docs.append(Document(page_content=keyword_content, metadata=metadata))

        # Vector document: annotation as content
        vector_docs.append(Document(page_content=annotation, metadata=metadata))

    logger.info("Loaded %d keyword docs and %d vector docs from %s", len(keyword_docs), len(vector_docs), index_path)
    return keyword_docs, vector_docs


def read_cheatsheet_content(cheatsheets_dir: str, cheatsheet_path: str) -> str:
    """
    Read markdown content of a specific grammar cheatsheet.

    Args:
        cheatsheets_dir: Base directory containing cheatsheets
        cheatsheet_path: Relative path to cheatsheet (e.g., "adjectives/adjectiv-komparation")

    Returns:
        Markdown content of the cheatsheet

    Raises:
        ValueError: If path contains traversal attempts
        FileNotFoundError: If cheatsheet file doesn't exist
    """
    # Prevent path traversal
    if ".." in cheatsheet_path or cheatsheet_path.startswith("/"):
        raise ValueError(f"Invalid cheatsheet path (path traversal detected): {cheatsheet_path}")

    base_dir = Path(cheatsheets_dir).resolve()
    cheatsheet_file = (base_dir / f"{cheatsheet_path}.md").resolve()

    # Ensure resolved path is within base directory
    if not str(cheatsheet_file).startswith(str(base_dir)):
        raise ValueError(f"Invalid cheatsheet path (outside base directory): {cheatsheet_path}")

    if not cheatsheet_file.exists():
        raise FileNotFoundError(f"Cheatsheet not found: {cheatsheet_path}")

    with open(cheatsheet_file, encoding="utf-8") as f:
        return f.read()
