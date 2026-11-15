"""Persistent Chroma vectorstore indexing and semantic querying for FasalBima Sathi."""
import json
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from app.chunking import get_all_chunks

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = ROOT / "data" / "chroma_db"
COLLECTION_NAME = "fasalbima_sathi_chunks"

_CLIENT = None
_COLLECTION = None


def get_chroma_collection(
    db_dir: Path | str = DEFAULT_DB_DIR,
    collection_name: str = COLLECTION_NAME,
):
    """Retrieve or create persistent Chroma collection."""
    global _CLIENT, _COLLECTION
    db_path = str(Path(db_dir).resolve())

    if _CLIENT is None or _COLLECTION is None:
        _CLIENT = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False, is_persistent=True),
        )
        _COLLECTION = _CLIENT.get_or_create_collection(
            name=collection_name,
            metadata={"description": "PMFBY Operational Guidelines & FAQ chunks"},
        )

    return _COLLECTION


def index_chunks(
    chunks: list[dict[str, Any]] | None = None,
    db_dir: Path | str = DEFAULT_DB_DIR,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 250,
    force_rebuild: bool = False,
) -> int:
    """Index document chunks into persistent Chroma collection."""
    collection = get_chroma_collection(db_dir, collection_name)

    existing_count = collection.count()
    if existing_count > 0 and not force_rebuild:
        logging.info("Chroma collection already contains %s chunks.", existing_count)
        return existing_count

    if force_rebuild and existing_count > 0:
        logging.info("Force rebuild requested: clearing existing collection.")
        # Delete and recreate
        client = chromadb.PersistentClient(path=str(Path(db_dir).resolve()))
        client.delete_collection(collection_name)
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "PMFBY Operational Guidelines & FAQ chunks"},
        )

    if chunks is None:
        chunks = get_all_chunks()

    total = len(chunks)
    logging.info("Indexing %s chunks into Chroma collection '%s'...", total, collection_name)

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        ids = [b["id"] for b in batch]
        documents = [b["text"] for b in batch]
        metadatas = [
            {
                "source": str(b.get("source", "")),
                "page": int(b.get("page", 1)),
                "title": str(b.get("title", "")),
                "og_version": str(b.get("og_version", "")),
            }
            for b in batch
        ]
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    indexed = collection.count()
    logging.info("Indexing complete! Total records in collection: %s", indexed)
    return indexed


def query_semantic(
    query: str,
    top_k: int = 5,
    db_dir: Path | str = DEFAULT_DB_DIR,
    collection_name: str = COLLECTION_NAME,
    where: dict | None = None,
) -> list[dict[str, Any]]:
    """Query Chroma collection and return ranked semantic results."""
    query = (query or "").strip()
    if not query or top_k <= 0:
        return []

    collection = get_chroma_collection(db_dir, collection_name)
    if collection.count() == 0:
        index_chunks(db_dir=db_dir, collection_name=collection_name)

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, max(1, collection.count())),
        where=where,
    )

    formatted = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(ids)

    for idx in range(len(ids)):
        dist = distances[idx] if idx < len(distances) else 0.0
        # Convert distance to a similarity score (0.0 to 1.0)
        sim_score = max(0.0, min(1.0, 1.0 - (dist / 2.0))) if dist is not None else 0.8
        meta = metas[idx] if idx < len(metas) else {}
        formatted.append(
            {
                "chunk_id": ids[idx],
                "score": round(sim_score, 4),
                "text": docs[idx] if idx < len(docs) else "",
                "source": meta.get("source", ""),
                "page": meta.get("page", 1),
                "title": meta.get("title", ""),
                "og_version": meta.get("og_version", ""),
            }
        )

    return formatted


def main():
    logging.basicConfig(level=logging.INFO)
    count = index_chunks(force_rebuild=False)
    print(f"Chroma index ready with {count} chunks.")
    test_q = "What is the deadline for localized hailstorm loss intimation?"
    hits = query_semantic(test_q, top_k=3)
    print(f"\nQuery: {test_q}")
    for h in hits:
        print(f"[{h['score']}] (Page {h['page']} - {h['title']}): {h['text'][:120]}...")


if __name__ == "__main__":
    main()

