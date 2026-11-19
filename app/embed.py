"""Embedding utilities and semantic search for FasalBima Sathi."""

import logging
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.json"

_GLOBAL_EMBEDDER = None


class FallbackDenseEmbedder:
    """Fast, deterministic, offline semantic embedding based on TF-IDF word & n-gram spaces."""

    def __init__(self, max_features: int = 512):
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=max_features,
            sublinear_tf=True,
        )
        self.is_fitted = False

    def fit(self, texts: list[str]) -> "FallbackDenseEmbedder":
        if texts:
            self.vectorizer.fit(texts)
            self.is_fitted = True
        return self

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self.is_fitted:
            self.fit(texts)
        mat = self.vectorizer.transform(texts).toarray()
        # L2-normalize
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = mat / norms
        return normalized.tolist()

    def embed_query(self, text: str) -> list[float]:
        if not self.is_fitted:
            self.fit([text])
        vec = self.vectorizer.transform([text]).toarray()[0]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


class EmbeddingEngine:
    """Unified embedding engine supporting sentence-transformers with reliable fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.st_model = None
        self.fallback = FallbackDenseEmbedder()
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer

            # Try to load local/cached model without hanging on remote timeout
            self.st_model = SentenceTransformer(self.model_name)
            logging.info("Loaded SentenceTransformer model: %s", self.model_name)
        except Exception as exc:
            logging.info("SentenceTransformer not loaded (%s); using dense TF-IDF embedder.", exc)
            self.st_model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.st_model is not None:
            try:
                embeddings = self.st_model.encode(
                    texts, convert_to_numpy=True, normalize_embeddings=True
                )
                return embeddings.tolist()
            except Exception as exc:
                logging.warning("SentenceTransformer encode failed (%s); using fallback.", exc)
        return self.fallback.embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        if self.st_model is not None:
            try:
                emb = self.st_model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
                return emb.tolist()
            except Exception as exc:
                logging.warning("SentenceTransformer query failed (%s); using fallback.", exc)
        return self.fallback.embed_query(query)


def get_embedder() -> EmbeddingEngine:
    global _GLOBAL_EMBEDDER
    if _GLOBAL_EMBEDDER is None:
        _GLOBAL_EMBEDDER = EmbeddingEngine()
    return _GLOBAL_EMBEDDER


def semantic_search_chunks(
    chunks: list[dict[str, Any]],
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rank document chunks by cosine similarity to query."""
    if not chunks or not query.strip() or top_k <= 0:
        return []

    embedder = get_embedder()
    texts = [c.get("text", "") for c in chunks]

    # Pre-fit fallback if not fitted
    if not embedder.fallback.is_fitted:
        embedder.fallback.fit(texts)

    query_vec = np.array(embedder.embed_query(query)).reshape(1, -1)
    doc_vecs = np.array(embedder.embed_texts(texts))

    scores = cosine_similarity(query_vec, doc_vecs).flatten()
    ranked_indices = scores.argsort()[::-1]

    results = []
    for idx in ranked_indices[:top_k]:
        score = float(scores[idx])
        c = chunks[idx]
        item = {
            "chunk_id": c.get("id"),
            "score": round(score, 4),
            "text": c.get("text"),
            "source": c.get("source"),
            "page": c.get("page"),
            "title": c.get("title"),
            "og_version": c.get("og_version"),
        }
        results.append(item)

    return results
