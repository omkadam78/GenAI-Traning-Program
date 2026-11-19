"""TF-IDF + cosine similarity smart search over PMFBY rule records."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _record_to_text(record: dict) -> str:
    """Combine key record fields into a single searchable text string."""
    parts = [
        str(record.get("rule_topic", "")),
        str(record.get("rule_topic", "")),  # slight boost for topic matches
        str(record.get("applies_to", "")),
        str(record.get("applies_to", "")),
        str(record.get("deadline_or_rate", "")),
        str(record.get("rule_text", "")),
        str(record.get("og_version", "")),
    ]
    return " ".join(p for p in parts if p).strip()


def smart_search(records: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """Rank records against a query using TF-IDF cosine similarity."""
    cleaned_query = (query or "").strip()
    if not cleaned_query or not records or top_k <= 0:
        return []

    corpus = [_record_to_text(r) for r in records]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(corpus + [cleaned_query])
    doc_vectors = matrix[:-1]
    query_vector = matrix[-1]

    scores = cosine_similarity(query_vector, doc_vectors).flatten()
    ranked_indices = scores.argsort()[::-1]

    results = []
    for idx in ranked_indices[:top_k]:
        score = float(scores[idx])
        if score <= 0.0:
            continue
        results.append(
            {
                "score": round(score, 4),
                **records[idx],
            }
        )
    return results
