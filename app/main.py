"""FastAPI service for FasalBima Sathi (Days 4–9)."""
from __future__ import annotations
import re
import uuid

from fastapi import FastAPI, HTTPException, Query, Header
from pydantic import BaseModel, Field

from app.agent_loop import run_agent_loop
from app.graph import run_langgraph_agent
from app.llm import generate_chat_response
from app.rag import ask_rag
from app.records import get_by_id, load_records
from app.smart_search import smart_search
from app.tools import pmfby_claim_deadline_check
from app.vectorstore import query_semantic
from pathlib import Path
import json
import logging
import threading
from datetime import datetime
import zoneinfo

import hashlib
from collections import OrderedDict
import time

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_FILE = ROOT / "data" / "feedback.jsonl"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
_FEEDBACK_LOCK = threading.Lock()


class IdempotencyManager:
    """Thread-safe, bounded idempotency manager with payload conflict detection and concurrent in-flight synchronization."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 1800):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.in_flight: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def _hash_payload(self, payload: AgentRequest) -> str:
        s = f"{payload.thread_id}|{payload.query}|{payload.approved}|{payload.calculation_id}|{payload.agent_type}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def check_or_register(self, request_id: str, payload: AgentRequest) -> tuple[dict | None, bool]:
        """Returns (cached_response, is_in_flight).
        
        Raises HTTPException(409) if the same request_id is reused with different payload parameters.
        """
        payload_hash = self._hash_payload(payload)
        now = time.time()

        with self.lock:
            # 1. Check existing cached response
            if request_id in self.cache:
                entry = self.cache[request_id]
                if now - entry["timestamp"] < self.ttl_seconds:
                    if entry["payload_hash"] != payload_hash:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Idempotency conflict: request_id '{request_id}' was previously submitted with different parameters.",
                        )
                    self.cache.move_to_end(request_id)
                    return entry["response"], False
                else:
                    del self.cache[request_id]

            # 2. Check if a request with this ID is currently being processed
            if request_id in self.in_flight:
                return None, True

            # Register new in-flight execution
            self.in_flight[request_id] = threading.Event()
            return None, False

    def wait_for_in_flight(self, request_id: str, timeout: float = 25.0) -> dict | None:
        event = None
        with self.lock:
            event = self.in_flight.get(request_id)
        if event:
            finished = event.wait(timeout=timeout)
            if finished:
                with self.lock:
                    if request_id in self.cache:
                        return self.cache[request_id]["response"]
        return None

    def store_response(self, request_id: str, payload: AgentRequest, response: dict) -> None:
        payload_hash = self._hash_payload(payload)
        now = time.time()
        with self.lock:
            if request_id in self.in_flight:
                self.in_flight[request_id].set()
                del self.in_flight[request_id]

            self.cache[request_id] = {
                "payload_hash": payload_hash,
                "response": response,
                "timestamp": now,
            }
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def release_on_error(self, request_id: str) -> None:
        with self.lock:
            if request_id in self.in_flight:
                self.in_flight[request_id].set()
                del self.in_flight[request_id]


_IDEMPOTENCY_MANAGER = IdempotencyManager()
idempotency_manager = _IDEMPOTENCY_MANAGER

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
    thread_id: str | None = Field(default=None, description="Session ID for stateful agent memory")
    approved: bool | None = Field(default=None, description="Approval flag (true to confirm, false to cancel)")
    calculation_id: str | None = Field(default=None, description="Pending calculation ID to bind approval")
    request_id: str | None = Field(default=None, description="Client request ID for idempotency")
    agent_type: str = Field(
        default="langgraph",
        pattern="^(langgraph|handwritten)$",
        description="Agent implementation: 'langgraph' (with memory & approval) or 'handwritten'",
    )
    max_iterations: int = Field(default=5, ge=1, le=10, description="Maximum reasoning/tool iterations")


class ClaimClockRequest(BaseModel):
    loss_timestamp: str = Field(..., min_length=1, description="Date/time of calamity (e.g. 'YYYY-MM-DD HH:MM', 'yesterday at 9 pm')")
    window_hours: int = Field(default=72, ge=1, le=168, description="Statutory intimation window (default 72 hours)")


class FeedbackRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Conversation session ID")
    response_id: str | None = Field(default=None, description="Assistant response ID being rated")
    query: str = Field(..., min_length=1, description="Farmer question")
    rating: str = Field(..., pattern="^(up|down)$", description="Rating: 'up' (thumbs up) or 'down' (thumbs down)")
    comment: str | None = Field(default=None, description="Optional farmer feedback comment")


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
def agent(
    payload: AgentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    """Day 9 endpoint: PMFBY agent with memory and human-in-the-loop approval step."""
    # 0. Check idempotency if request_id or header is supplied
    req_id = payload.request_id or idempotency_key or x_request_id
    if req_id:
        payload.request_id = req_id
        cached_resp, is_in_flight = _IDEMPOTENCY_MANAGER.check_or_register(req_id, payload)
        if cached_resp is not None:
            return cached_resp
        if is_in_flight:
            waited_resp = _IDEMPOTENCY_MANAGER.wait_for_in_flight(req_id, timeout=25.0)
            if waited_resp is not None:
                return waited_resp

    # 1. Reject empty or whitespace-only queries when approved is not passed
    if payload.query is not None and not payload.query.strip() and payload.approved is None:
        if payload.request_id:
            _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
        raise HTTPException(status_code=400, detail="Query cannot be empty or whitespace.")

    # 2. Reject request with neither query nor approved flag
    if payload.query is None and payload.approved is None:
        if payload.request_id:
            _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
        raise HTTPException(status_code=400, detail="Either 'query' or 'approved' must be provided.")

    # 3. For approval/resume, require both thread_id AND calculation_id
    if payload.approved is not None:
        if not payload.thread_id or not payload.thread_id.strip():
            if payload.request_id:
                _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
            raise HTTPException(
                status_code=400,
                detail="A valid 'thread_id' is required to resume or cancel a pending calculation.",
            )
        if not payload.calculation_id or not payload.calculation_id.strip():
            if payload.request_id:
                _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
            raise HTTPException(
                status_code=400,
                detail="A valid 'calculation_id' is required to approve or cancel a pending calculation.",
            )

    if payload.agent_type == "handwritten":
        if not payload.query or not payload.query.strip():
            if payload.request_id:
                _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
            raise HTTPException(status_code=400, detail="query is required for handwritten agent")
        try:
            result = run_agent_loop(payload.query, max_iterations=payload.max_iterations)
            result["thread_id"] = payload.thread_id or f"session_{uuid.uuid4().hex[:12]}"
            result["agent_type"] = "handwritten"
            if payload.request_id:
                _IDEMPOTENCY_MANAGER.store_response(payload.request_id, payload, result)
            return result
        except Exception as err:
            if payload.request_id:
                _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
            raise HTTPException(status_code=500, detail=f"Agent loop error: {err}")

    try:
        result = run_langgraph_agent(
            query=payload.query,
            thread_id=payload.thread_id,
            approved=payload.approved,
            calculation_id=payload.calculation_id,
        )
        result["agent_type"] = "langgraph"
        if payload.request_id:
            _IDEMPOTENCY_MANAGER.store_response(payload.request_id, payload, result)
        return result
    except Exception as err:
        if payload.request_id:
            _IDEMPOTENCY_MANAGER.release_on_error(payload.request_id)
        raise HTTPException(status_code=500, detail=f"Agent processing error: {err}")


@app.post("/claim-clock")
def check_claim_clock(payload: ClaimClockRequest):
    """Day 10 signature feature: 72-hour localized calamity intimation clock."""
    try:
        clock_res = pmfby_claim_deadline_check(
            loss_timestamp=payload.loss_timestamp,
            window_hours=payload.window_hours,
        )
        return clock_res
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Claim clock calculation failed: {err}")


@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):
    """Day 10 endpoint: Collect thumbs up/down user feedback with deduplication by response_id."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _FEEDBACK_LOCK:
        existing_entries = []
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            existing_entries.append(json.loads(line))
                        except Exception:
                            pass

        # Deduplicate by (thread_id, response_id) or (thread_id, query) if response_id omitted
        resp_id = payload.response_id or f"resp_legacy_{uuid.uuid4().hex[:6]}"
        updated = False
        new_entry = {
            "id": f"fb_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(tz=IST).isoformat(),
            "thread_id": payload.thread_id,
            "response_id": resp_id,
            "query": payload.query,
            "rating": payload.rating,
            "comment": payload.comment,
        }

        for idx, entry in enumerate(existing_entries):
            match_found = False
            if payload.response_id:
                match_found = (entry.get("thread_id") == payload.thread_id and entry.get("response_id") == payload.response_id)
            else:
                match_found = (entry.get("thread_id") == payload.thread_id and entry.get("query") == payload.query)

            if match_found:
                existing_entries[idx] = new_entry
                updated = True
                break

        if not updated:
            existing_entries.append(new_entry)

        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            for entry in existing_entries:
                f.write(json.dumps(entry) + "\n")

    return {"status": "success", "updated": updated, "entry": new_entry}


@app.get("/feedback")
def list_feedback(
    thread_id: str = Query(..., min_length=1, description="Session ID required to retrieve feedback records"),
):
    """Retrieve collected feedback records for the specified session thread_id.

    Protects farmer privacy by strictly scoping feedback retrieval to the active session.
    """
    if not FEEDBACK_FILE.exists():
        return {"count": 0, "feedback": []}

    with _FEEDBACK_LOCK:
        entries = []
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

    entries = [e for e in entries if e.get("thread_id") == thread_id]
    return {"count": len(entries), "feedback": entries}

