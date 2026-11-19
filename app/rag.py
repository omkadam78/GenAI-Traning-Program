"""Retrieval-Augmented Generation (RAG) pipeline for FasalBima Sathi."""

from pathlib import Path
from typing import Any

from app.llm import generate_chat_response, is_personal_claim_query
from app.vectorstore import query_semantic

ROOT = Path(__file__).resolve().parents[1]

DISCLAIMER = (
    "Information from official PMFBY guidelines, not insurance or legal advice. "
    "Claim decisions rest with the insurance company and the state government."
)


def ask_rag(
    question: str,
    top_k: int = 3,
    prompt_version: str = "v2",
    collection_name: str = "fasalbima_sathi_chunks",
) -> dict[str, Any]:
    """Answer PMFBY questions from retrieved vectorstore chunks with citations.

    Strictly refuses private claim status inquiries (Q6) with an honest 'I don't know'.
    """
    cleaned_q = (question or "").strip()

    # Mandatory Safety Grounding Rule: Refuse unanswerable personal status queries
    if is_personal_claim_query(cleaned_q):
        return {
            "question": cleaned_q,
            "answered": False,
            "answer": (
                "I don't know. PMFBY official guideline documents do not contain "
                "personal farmer claim approvals, individual application statuses, or bank payment confirmations. "
                "Please verify your application status directly on pmfby.gov.in (NCIP), "
                "through the official Crop Insurance App, or by calling Krishi Rakshak Helpline 14447."
            ),
            "confidence": 0.0,
            "citations": [],
            "retrieved_chunks": [],
            "disclaimer": DISCLAIMER,
        }

    # Retrieve relevant document chunks from Chroma
    chunks = query_semantic(cleaned_q, top_k=top_k, collection_name=collection_name)

    # Minimum relevance score threshold to prevent hallucination on irrelevant queries
    EVIDENCE_THRESHOLD = 0.25
    valid_chunks = [c for c in chunks if c.get("score", 0.0) >= EVIDENCE_THRESHOLD]

    if not valid_chunks:
        return {
            "question": cleaned_q,
            "answered": False,
            "answer": "I don't know. No relevant PMFBY guidelines were found in the knowledge base.",
            "confidence": 0.0,
            "citations": [],
            "retrieved_chunks": [],
            "disclaimer": DISCLAIMER,
        }

    # Format retrieved chunks for citations and synthesis
    citations = [
        {
            "chunk_id": c.get("chunk_id", ""),
            "source": c.get("source", ""),
            "page": c.get("page", 1),
            "title": c.get("title", ""),
            "og_version": c.get("og_version", ""),
            "relevance_score": c.get("score", 0.0),
        }
        for c in valid_chunks
    ]

    # Convert chunks to record format for LLM wrapper synthesis
    adapted_records = []
    for c in valid_chunks:
        adapted_records.append(
            {
                "id": c.get("chunk_id", 0),
                "rule_topic": c.get("title", "PMFBY Guideline"),
                "rule_text": c.get("text", ""),
                "og_version": c.get("og_version", "Revamped OG (Kharif 2020)"),
                "applies_to": f"Page {c.get('page', 1)} of {c.get('source', '')}",
                "deadline_or_rate": "Refer to cited section",
                "source_url": c.get("source", ""),
                "score": c.get("score", 0.0),
            }
        )

    # Generate grounded response
    llm_res = generate_chat_response(
        question=cleaned_q,
        prompt_version=prompt_version,
        top_k=top_k,
        context_records=adapted_records,
    )

    answer_text = llm_res.get("answer", "")
    low_answer = answer_text.strip().casefold()
    is_abstention = (
        low_answer.startswith("i don't know")
        or low_answer.startswith("i do not know")
        or "cannot determine" in low_answer
        or "no information" in low_answer
    )

    if is_abstention:
        return {
            "question": cleaned_q,
            "answered": False,
            "answer": answer_text,
            "confidence": 0.0,
            "follow_up": llm_res.get("follow_up", ""),
            "citations": citations,
            "retrieved_chunks": valid_chunks,
            "disclaimer": DISCLAIMER,
            "provider": llm_res.get("provider", "rag-engine"),
            "model": llm_res.get("model", "pmfby-rag-v1"),
        }

    # Compute grounded confidence from top chunk relevance score
    top_score = float(valid_chunks[0].get("score", 0.8))
    grounded_confidence = round(max(0.5, min(0.98, top_score)), 2)

    return {
        "question": cleaned_q,
        "answered": True,
        "answer": answer_text,
        "confidence": grounded_confidence,
        "follow_up": llm_res.get("follow_up", ""),
        "citations": citations,
        "retrieved_chunks": valid_chunks,
        "disclaimer": DISCLAIMER,
        "provider": llm_res.get("provider", "rag-engine"),
        "model": llm_res.get("model", "pmfby-rag-v1"),
    }
