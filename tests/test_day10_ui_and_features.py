"""Unit and regression tests for Day 10 UI, LangGraph interrupt, claim clock, and feedback."""

from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.graph import run_langgraph_agent
from app.main import app
from app.tools import (
    IST,
    pmfby_premium,
)

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_FILE = ROOT / "data" / "feedback.jsonl"
FIXED_NOW = datetime(2026, 11, 18, 10, 0, 0, tzinfo=IST)


def test_units_isolation_and_conversions():
    # 1. Area in acres with Scale of Finance per acre
    res_both_acres = pmfby_premium(
        scale_of_finance=25000,
        area=4.0,
        area_unit="acre",
        scale_of_finance_unit="per_acre",
        crop="soybean",
    )
    # Sum insured = 25000 * 4 = 100,000
    assert res_both_acres["sum_insured"] == 100000.0
    # Farmer premium = 2.0% of 100,000 = 2,000
    assert res_both_acres["farmer_premium"] == 2000.0
    assert res_both_acres["area_unit"] == "acre"
    assert res_both_acres["scale_of_finance_unit"] == "per_acre"

    # 2. Area in acres with Scale of Finance per ha
    res_mixed = pmfby_premium(
        scale_of_finance=49000,
        area=2.471054,
        area_unit="acre",
        scale_of_finance_unit="per_ha",
        crop="soybean",
    )
    # 2.471054 acres = 1.0 ha -> Sum insured = 49000
    assert abs(res_mixed["sum_insured"] - 49000.0) < 1.0
    assert res_mixed["area_unit"] == "acre"
    assert res_mixed["scale_of_finance_unit"] == "per_ha"

    # 3. Reject unsupported scale of finance unit
    with pytest.raises(ValueError, match="Unsupported scale of finance unit"):
        pmfby_premium(
            scale_of_finance=49000,
            area=2.0,
            scale_of_finance_unit="per_bigha",
            crop="soybean",
        )


def test_compound_question_handling():
    # Compound question with both premium and calamity intimation
    q = (
        "Calculate soybean premium for 2 ha at scale of finance 49000 and "
        "what is the deadline if hailstorm hit yesterday at 9 pm?"
    )
    res = run_langgraph_agent(q)
    assert res["status"] == "approval_required"
    assert res["requires_approval"] is True
    # Verify that the calamity deadline information is presented
    assert "Localized Calamity Intimation" in res["answer"]
    assert "Approval Required" in res["answer"]


def test_langgraph_native_interrupt_and_cancellation():
    sess = "test_sess_interrupt_cancel_42"
    q = "Calculate soybean premium for 1.5 ha with scale of finance 49000"

    # Step 1: Pauses at interrupt
    r1 = run_langgraph_agent(query=q, thread_id=sess)
    assert r1["status"] == "approval_required"
    assert r1["requires_approval"] is True
    calc_id = r1["pending_calculation"]["id"]

    # Step 2: Cancel
    r2 = run_langgraph_agent(thread_id=sess, approved=False, calculation_id=calc_id)
    assert r2["status"] == "cancelled"
    assert r2["requires_approval"] is False
    assert r2["tool_calls"] == []
    assert "cancelled as requested" in r2["answer"].lower()

    # Step 3: Verify no tool ran and subsequent resume attempt is rejected
    r3 = run_langgraph_agent(thread_id=sess, approved=True, calculation_id=calc_id)
    assert r3["status"] == "rejected"
    assert "No pending calculation" in r3["answer"]


def test_claim_clock_api_and_reporting_channels():
    # Active window
    payload_active = {"loss_timestamp": "2026-11-17 12:00", "window_hours": 72}
    r1 = client.post("/claim-clock", json=payload_active)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["window_hours"] == 72
    assert len(data1["reporting_channels"]) >= 4
    assert any("Crop Insurance App" in ch for ch in data1["reporting_channels"])
    assert any("14447" in ch for ch in data1["reporting_channels"])

    # Reject future date
    payload_future = {"loss_timestamp": "2029-01-01 10:00"}
    r2 = client.post("/claim-clock", json=payload_future)
    assert r2.status_code == 400
    assert "future" in r2.json()["detail"].lower()


def test_feedback_submission_and_deduplication():
    thread_id = "test_feedback_sess_100"
    query = "What is the statutory deadline for hailstorm loss?"

    # Submit first rating: 'up'
    r1 = client.post(
        "/feedback",
        json={"thread_id": thread_id, "query": query, "rating": "up", "comment": "Clear response"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "success"

    # Submit second rating for SAME thread and query: 'down' -> Must deduplicate/update
    r2 = client.post(
        "/feedback",
        json={"thread_id": thread_id, "query": query, "rating": "down", "comment": "Changed mind"},
    )
    assert r2.status_code == 200
    assert r2.json()["updated"] is True

    # Check GET /feedback (scoped by thread_id)
    r_list = client.get(f"/feedback?thread_id={thread_id}")
    assert r_list.status_code == 200
    fb_list = r_list.json()["feedback"]
    matching = [e for e in fb_list if e.get("thread_id") == thread_id and e.get("query") == query]
    assert len(matching) == 1
    assert matching[0]["rating"] == "down"
