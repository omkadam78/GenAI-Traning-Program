"""FastAPI service for FasalBima Sathi (Days 4–9)."""
import re

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.agent_loop import run_agent_loop
from app.graph import run_langgraph_agent
from app.llm import generate_chat_response
from app.rag import ask_rag
from app.records import get_by_id, load_records
from app.smart_search import smart_search
from app.vectorstore import query_semantic

DISCLAIMER = (
    "Information from official PMFBY guidelines, not insurance or legal advice. "
    "Claim decisions rest with the insurance company and the state government."
)

OUT_OF_SCOPE_PATTERNS = (
    r"\bmy\s+(?:pmfby\s+)?claim\b.*\bapproved\b",
    r"\bclaim\s+status\b",
    r"\bapplication\s+(?:status|number)\b",
    r"\bhas\s+my\b.*\bapproved\b",
    r"\bpolicy\s+status\b",
    r"\bcredit(?:ed)?\s+to\s+my\s+bank\b",
    r"\b(?:compensation|payment|money|amount)\b.*\b(?:reached|account|bank|sbi)\b",
    r"\bcheck\s+if\s+my\b",
)

app = FastAPI(
    title="FasalBima Sathi API",
    description="PMFBY crop insurance assistant with rule lookup, LLM chat, Chroma RAG, and LangGraph agent.",
    version="0.9.0",
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Farmer crop insurance question")
    top_k: int = Field(default=3, ge=1, le=10)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Farmer message or inquiry")
    prompt_version: str = Field(
        default="v2",
        pattern="^(v1|v2)$",
        description="Prompt version: 'v1' (concise) or 'v2' (detailed structured)",
    )
    top_k: int = Field(default=3, ge=1, le=10)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Farmer crop insurance question")
    top_k: int = Field(default=3, ge=1, le=10)
    prompt_version: str = Field(default="v2", pattern="^(v1|v2)$")


class AgentRequest(BaseModel):
    query: str | None = Field(default=None, description="Farmer query or calculation request")
    thread_id: str = Field(default="default_thread", description="Thread ID for stateful agent memory")
    approved: bool | None = Field(default=None, description="Approval flag for human-in-the-loop confirmation")
    agent_type: str = Field(
        default="langgraph",
        pattern="^(langgraph|handwritten)$",
        description="Agent implementation: 'langgraph' (with memory & approval) or 'handwritten'",
    )


def _is_personal_status_query(question: str) -> bool:
    """Detect individual claim/policy status questions that static rules cannot answer."""
    q = question.strip().casefold()
    return any(re.search(pat, q) for pat in OUT_OF_SCOPE_PATTERNS)


@app.get("/health")
def health():
    records = load_records()
    return {
        "status": "ok",
        "product": "FasalBima Sathi",
        "records_count": len(records),
        "disclaimer": DISCLAIMER,
    }


@app.get("/records")
def list_records(limit: int | None = Query(default=None, ge=1, le=200)):
    records = load_records()
    subset = records[:limit] if limit is not None else records
    return {"count": len(subset), "records": subset}


@app.get("/records/{record_id}")
def read_record(record_id: int):
    records = load_records()
    record = get_by_id(records, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return record


@app.get("/search")
def search_records(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=5, ge=1, le=50),
):
    records = load_records()
    results = smart_search(records, q, top_k=limit)
    return {"query": q, "count": len(results), "results": results}


@app.get("/search/semantic")
def search_semantic(
    q: str = Query(..., min_length=1, description="Semantic search query"),
    limit: int = Query(default=5, ge=1, le=50),
):
    """Day 7 endpoint: semantic search over Chroma vectorstore collection."""
    results = query_semantic(q, top_k=limit)
    return {
        "query": q,
        "count": len(results),
        "results": results,
    }


@app.post("/questions")
def ask_question(payload: QuestionRequest):
    if _is_personal_status_query(payload.question):
        return {
            "question": payload.question,
            "answered": False,
            "answer": (
                "I don't know. Static PMFBY guideline records cannot check individual "
                "farmer claim approval or policy status. Please verify directly on "
                "pmfby.gov.in (NCIP), the Crop Insurance App, or Krishi Rakshak Helpline 14447."
            ),
            "citations": [],
            "disclaimer": DISCLAIMER,
        }

    records = load_records()
    matches = smart_search(records, payload.question, top_k=payload.top_k)
    if not matches:
        return {
            "question": payload.question,
            "answered": False,
            "answer": "I don't know. No matching PMFBY rule was found in the loaded dataset.",
            "citations": [],
            "disclaimer": DISCLAIMER,
        }

    ordered = sorted(
        matches,
        key=lambda m: (
            1 if "Revamped OG" in m.get("og_version", "") else 0,
            m["score"],
        ),
        reverse=True,
    )
    top = ordered[0]
    summary_parts = [
        f"{m['rule_topic']} ({m['og_version']}): {m['rule_text']} [Rate/Timeline: {m['deadline_or_rate']}]"
        for m in ordered[: payload.top_k]
    ]
    return {
        "question": payload.question,
        "answered": True,
        "answer": " | ".join(summary_parts),
        "primary_version": top["og_version"],
        "citations": [
            {
                "id": m["id"],
                "rule_topic": m["rule_topic"],
                "og_version": m["og_version"],
                "deadline_or_rate": m["deadline_or_rate"],
                "source_url": m["source_url"],
                "score": m["score"],
            }
            for m in ordered
        ],
        "disclaimer": DISCLAIMER,
    }


@app.post("/chat")
def chat(payload: ChatRequest):
    """Day 6 endpoint: returns JSON with answer, confidence, and follow_up."""
    response = generate_chat_response(
        question=payload.message,
        prompt_version=payload.prompt_version,
        top_k=payload.top_k,
    )
    response["disclaimer"] = DISCLAIMER
    return response


@app.post("/ask")
def ask(payload: AskRequest):
    """Day 8 endpoint: answer questions from retrieved chunks with citations; must say 'I don't know' for Q6."""
    return ask_rag(
        question=payload.question,
        top_k=payload.top_k,
        prompt_version=payload.prompt_version,
    )


@app.post("/agent")
def agent(payload: AgentRequest):
    """Day 9 endpoint: PMFBY agent with memory and human-in-the-loop approval step."""
    if payload.agent_type == "handwritten":
        if not payload.query:
            raise HTTPException(status_code=400, detail="query is required for handwritten agent")
        result = run_agent_loop(payload.query)
        result["thread_id"] = payload.thread_id
        result["agent_type"] = "handwritten"
        result["status"] = "completed"
        result["requires_approval"] = False
        return result

    result = run_langgraph_agent(
        query=payload.query,
        thread_id=payload.thread_id,
        approved=payload.approved,
    )
    result["agent_type"] = "langgraph"
    return result

