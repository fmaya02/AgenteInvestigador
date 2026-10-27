"""Ingesta del RAG: documentos -> chunks -> embeddings -> Chroma.

Se ejecuta una vez (y de nuevo cada vez que cambien los documentos), desde la
carpeta del proyecto:   python -m rag.ingest
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.store import DB_DIR, DOCS_DIR, get_store


def main() -> None:
    # 1. Cargar: cada archivo es un Document, con su nombre como metadata.
    archivos = [p for p in sorted(DOCS_DIR.iterdir()) if p.suffix in {".md", ".txt"}]
    if not archivos:
        raise SystemExit(f"No hay archivos .md o .txt en {DOCS_DIR}")
    documentos = [
        Document(page_content=p.read_text(encoding="utf-8"), metadata={"source": p.name})
        for p in archivos
    ]

    # 2. Chunking: la metadata del documento se hereda en cada chunk.
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(documentos)

    # 3 y 4. Embeddings + base vectorial. Se reinicia la colección para no duplicar.
    store = get_store()
    store.reset_collection()
    store.add_documents(chunks)

    print(f"{len(documentos)} documentos -> {len(chunks)} chunks indexados en {DB_DIR}")


if __name__ == "__main__":
    main()