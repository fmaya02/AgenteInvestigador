"""Base vectorial del RAG: rutas y acceso compartidos por la ingesta y la tool."""
from pathlib import Path

from langchain_chroma import Chroma

from model import get_embeddings

RAG_DIR = Path(__file__).parent
DOCS_DIR = RAG_DIR / "docs"          # documentos fuente (.md / .txt)
DB_DIR = RAG_DIR / "chroma_db"       # base vectorial persistida en disco


def get_store() -> Chroma:
    return Chroma(
        collection_name="conocimiento",
        embedding_function=get_embeddings(),
        persist_directory=str(DB_DIR),
    )