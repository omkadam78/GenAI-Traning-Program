"""Unit and regression tests for Unified LLM Provider, Idempotency, Timezone Handling, and Security."""
from datetime import datetime, timezone, timedelta
import json
import threading
import time
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app, idempotency_manager
from app.llm import (
    generate_chat_response,
    _call_groq_api,
    _call_gemini_api,
    LLMAuthenticationError,
    LLMError,
)
from app.tools import IST
from ui.app import parse_iso_datetime

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Timezone-Aware ISO Parsing Tests (Live Claim Clock)
# ---------------------------------------------------------------------------

def test_parse_iso_datetime_with_ist_offset():
    """Verify ISO string with +05:30 offset parses into IST datetime."""
    dt_str = "2026-11-18T14:30:00+05:30"
    dt = parse_iso_datetime(dt_str)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.hour == 14
    assert dt.minute == 30
    # Verify offset is 5 hours 30 mins
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


def test_parse_iso_datetime_with_utc_z():
    """Verify ISO string with UTC 'Z' converts accurately to IST."""
    dt_str = "2026-11-18T09:00:00Z"
    dt = parse_iso_datetime(dt_str)
    assert dt is not None
    # 09:00 UTC == 14:30 IST (+5:30)
    assert dt.hour == 14
    assert dt.minute == 30
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


def test_parse_iso_datetime_with_ist_label():
    """Verify string ending with ' IST' normalizes and parses into IST."""
    dt_str = "2026-11-18 10:00:00 IST"
    dt = parse_iso_datetime(dt_str)
    assert dt is not None
    assert dt.hour == 10
    assert dt.minute == 0
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


def test_parse_iso_datetime_naive():
    """Verify naive ISO string defaults to IST without crash."""
    dt_str = "2026-11-18T16:00:00"
    dt = parse_iso_datetime(dt_str)
    assert dt is not None
    assert dt.hour == 16
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


def test_parse_iso_datetime_invalid():
    """Verify invalid format returns None gracefully."""
    assert parse_iso_datetime("not-a-valid-date-string") is None
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime(None) is None


# ---------------------------------------------------------------------------
# 2. Idempotency Manager Tests (Deduplication, Conflict, Concurrency)
# ---------------------------------------------------------------------------

def test_idempotency_cache_hit():
    """Verify repeating a request with same Idempotency-Key returns cached response."""
    idem_key = "test-idem-key-101"
    payload = {
        "query": "What is the premium rate for wheat in Rabi?",
        "thread_id": "thread_idem_1",
    }
    r1 = client.post("/agent", json=payload, headers={"Idempotency-Key": idem_key})
    assert r1.status_code == 200
    data1 = r1.json()

    # Second request with EXACT same key and payload
    r2 = client.post("/agent", json=payload, headers={"Idempotency-Key": idem_key})
    assert r2.status_code == 200
    data2 = r2.json()

    assert data1["response_id"] == data2["response_id"]
    assert data1["answer"] == data2["answer"]


def test_idempotency_payload_conflict_409():
    """Verify same Idempotency-Key with DIFFERENT payload raises HTTP 409 Conflict."""
    idem_key = "test-idem-key-conflict-409"
    payload1 = {
        "query": "Soybean rate Kharif",
        "thread_id": "thread_idem_2",
    }
    payload2 = {
        "query": "Wheat rate Rabi",
        "thread_id": "thread_idem_2",
    }

    r1 = client.post("/agent", json=payload1, headers={"Idempotency-Key": idem_key})
    assert r1.status_code == 200

    # Conflict request
    r2 = client.post("/agent", json=payload2, headers={"Idempotency-Key": idem_key})
    assert r2.status_code == 409
    assert "Idempotency conflict" in r2.json()["detail"]


def test_idempotency_concurrent_in_flight():
    """Verify concurrent requests with same key synchronize and do not duplicate execution."""
    idem_key = f"test-concurrent-{time.time()}"
    payload = {
        "query": "What is PMFBY cut off date for Rabi?",
        "thread_id": "thread_concurrent",
    }

    results = []

    def make_request():
        r = client.post("/agent", json=payload, headers={"Idempotency-Key": idem_key})
        results.append(r)

    t1 = threading.Thread(target=make_request)
    t2 = threading.Thread(target=make_request)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    assert results[0].status_code == 200
    assert results[1].status_code == 200
    assert results[0].json()["response_id"] == results[1].json()["response_id"]


# ---------------------------------------------------------------------------
# 3. Security: Scoped Feedback Endpoint Tests
# ---------------------------------------------------------------------------

def test_feedback_requires_thread_id():
    """Verify GET /feedback without thread_id query parameter returns 422 Unprocessable Entity."""
    r = client.get("/feedback")
    assert r.status_code == 422  # FastAPI validation error for missing required query param


def test_feedback_empty_thread_id_rejected():
    """Verify GET /feedback with empty thread_id returns 422."""
    r = client.get("/feedback?thread_id=")
    assert r.status_code == 422


def test_feedback_scoped_isolation():
    """Verify GET /feedback?thread_id=X only returns feedback for thread X."""
    # Post feedback for thread_A
    client.post(
        "/feedback",
        json={"thread_id": "thread_A", "query": "Q_A", "rating": "up"},
    )
    # Post feedback for thread_B
    client.post(
        "/feedback",
        json={"thread_id": "thread_B", "query": "Q_B", "rating": "down"},
    )

    r_a = client.get("/feedback?thread_id=thread_A")
    assert r_a.status_code == 200
    fb_a = r_a.json()["feedback"]
    assert all(item["thread_id"] == "thread_A" for item in fb_a)

    r_b = client.get("/feedback?thread_id=thread_B")
    assert r_b.status_code == 200
    fb_b = r_b.json()["feedback"]
    assert all(item["thread_id"] == "thread_B" for item in fb_b)


# ---------------------------------------------------------------------------
# 4. LLM Provider Interface, Offline Fallback & Reliability Tests
# ---------------------------------------------------------------------------

def test_llm_offline_fallback_when_keys_missing():
    """When no API keys are set, generate_chat_response must return deterministic-rule-engine."""
    with patch.dict("os.environ", {"GROQ_API_KEY": "", "GEMINI_API_KEY": ""}):
        res = generate_chat_response(
            question="What is the claim intimation window for localized calamity?",
            prompt_version="v2",
            top_k=2,
            context_records=[
                {
                    "rule_topic": "Localized Calamity Claim Intimation Window",
                    "rule_text": "Loss must be reported within 72 hours of occurrence.",
                    "og_version": "Revamped OG 2020",
                    "applies_to": "All notified crops",
                    "deadline_or_rate": "72 hours",
                    "source_url": "pmfby_guidelines.pdf",
                }
            ],
        )
        assert res["provider"] == "deterministic-rule-engine"
        assert res["model"] == "pmfby-offline-v1"
        assert res["fallback_occurred"] is False
        assert "72 hours" in res["answer"]
        assert 0.0 <= res["confidence"] <= 1.0


def test_llm_groq_mock_success():
    """Verify Groq API parsing and usage metadata when mock returns valid response."""
    mock_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "answer": "Loss must be reported within 72 hours via the Crop Insurance App.",
                        "confidence": 0.95,
                        "follow_up": "Do you need the toll-free helpline number?",
                    })
                }
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 35, "total_tokens": 155},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("requests.post", return_value=mock_resp):
        res = _call_groq_api(
            api_key="gsk_mock_key_valid",
            model="llama-3.3-70b-versatile",
            system_prompt="You are FasalBima Sathi.",
            user_prompt="Explain claim deadline.",
        )

        assert "raw_text" in res
        assert "72 hours" in res["raw_text"]
        assert res["usage"]["total_tokens"] == 155


def test_llm_automatic_secondary_fallback():
    """Verify that when primary provider fails, the secondary provider is automatically invoked."""
    mock_gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "answer": "Gemini fallback: Report within 72 hours.",
                                "confidence": 0.92,
                                "follow_up": "Would you like help calculating premium?",
                            })
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 80, "candidatesTokenCount": 25, "totalTokenCount": 105},
    }

    groq_resp = MagicMock()
    groq_resp.status_code = 500
    groq_resp.headers = {}
    groq_resp.text = "Internal Server Error"

    gemini_resp = MagicMock()
    gemini_resp.status_code = 200
    gemini_resp.json.return_value = mock_gemini_payload

    def mock_post(url, *args, **kwargs):
        if "groq.com" in url:
            return groq_resp
        return gemini_resp

    with patch.dict("os.environ", {
        "GROQ_API_KEY": "gsk_primary_key",
        "GEMINI_API_KEY": "AIzaSy_secondary_key",
        "LLM_PROVIDER": "groq",
    }):
        with patch("requests.post", side_effect=mock_post):
            res = generate_chat_response(
                question="What is the deadline?",
                prompt_version="v2",
                top_k=1,
                context_records=[{"rule_topic": "Intimation", "rule_text": "72h window"}],
            )

            assert res["provider"] == "gemini"
            assert res["fallback_occurred"] is True
            assert "Gemini fallback" in res["answer"]


def test_llm_auth_failure_raises_immediately():
    """Verify that HTTP 401 Authentication failure raises LLMAuthenticationError immediately."""
    auth_resp = MagicMock()
    auth_resp.status_code = 401
    auth_resp.text = "Invalid API Key"

    with patch("requests.post", return_value=auth_resp) as mock_post:
        with pytest.raises(LLMAuthenticationError, match="Groq API authentication failed"):
            _call_groq_api(
                api_key="gsk_bad_key",
                model="llama-3.3-70b-versatile",
                system_prompt="system",
                user_prompt="user",
                max_retries=3,
            )
        # Verify it did NOT retry 3 times on 401
        assert mock_post.call_count == 1
