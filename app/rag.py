"""Retrieval-Augmented Generation (RAG) pipeline for FasalBima Sathi."""
import logging
from pathlib import Path
import re
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
    chunks = query_semantic(cleaned_q, top_k=top_k)

    if not chunks:
        return {
            "question": cleaned_q,
            "answered": False,
            "answer": "I don't know. No relevant PMFBY guidelines were found in the knowledge base.",
            "confidence": 0.2,
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
        for c in chunks
    ]

    # Convert chunks to record format for LLM wrapper synthesis
    adapted_records = []
    for c in chunks:
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

    return {
        "question": cleaned_q,
        "answered": True,
        "answer": llm_res.get("answer", ""),
        "confidence": llm_res.get("confidence", 0.95),
        "follow_up": llm_res.get("follow_up", ""),
        "citations": citations,
        "retrieved_chunks": chunks,
        "disclaimer": DISCLAIMER,
        "provider": llm_res.get("provider", "rag-engine"),
        "model": llm_res.get("model", "pmfby-rag-v1"),
    }

