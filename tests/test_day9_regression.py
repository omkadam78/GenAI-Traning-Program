"""Comprehensive regression tests for Day 9 PMFBY agent implementation fixes.

Covers:
- Normal premium calculations and actuarial rate below the statutory cap.
- Missing and invalid inputs (bool, NaN, inf, negative, zero, missing crop/season).
- Missing rate evidence handling.
- Acres to hectares conversion and unsupported unit rejection.
- Approval lifecycle: pause, approve/resume, replay protection, approval reset, and cancellation.
- New knowledge question after a completed calculation (no param reuse).
- Memory isolation between different conversation IDs.
- Actual timestamp parsing, relative dates with fixed clock, expired timestamps, and invalid date rejection.
- Tool failures, refusal behavior, and truthful tool traces.
- FastAPI POST /agent endpoint validations and error handling.
"""
from datetime import datetime
from decimal import Decimal
import zoneinfo
import pytest
from fastapi.testclient import TestClient

from app.agent_loop import run_agent_loop
from app.graph import run_langgraph_agent
from app.main import app
from app.tools import (
    IST,
    pmfby_claim_deadline_check,
    pmfby_knowledge_search,
    pmfby_premium,
)

client = TestClient(app)
FIXED_NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=IST)


# ---------------------------------------------------------------------------
# 1. Premium tool: normal calculations and actuarial below cap
# ---------------------------------------------------------------------------
def test_pmfby_premium_normal_and_actuarial_rate():
    # Scenario A: Kharif Soybean (2.0% statutory cap, no actuarial rate provided -> estimated max)
    res_soy = pmfby_premium(scale_of_finance=49000, area=1.2, crop="soybean", season="kharif")
    assert res_soy["sum_insured"] == 58800.0
    assert res_soy["farmer_rate_percent"] == 2.0
    assert res_soy["farmer_premium"] == 1176.0
    assert res_soy["is_estimated_maximum"] is True
    assert "Estimated maximum" in res_soy["rate_note"]

    # Scenario B: Actuarial tender rate is known and BELOW statutory cap (e.g. 1.2% < 2.0%)
    res_act = pmfby_premium(
        scale_of_finance=49000, area=1.2, crop="soybean", season="kharif", actuarial_rate=1.2
    )
    assert res_act["farmer_rate_percent"] == 1.2
    assert res_act["farmer_premium"] == 705.60
    assert res_act["is_estimated_maximum"] is False
    assert res_act["govt_subsidy"] == 0.0

    # Scenario C: Rabi Wheat (1.5% statutory cap)
    res_wheat = pmfby_premium(scale_of_finance=40000, area=2.0, crop="wheat", season="rabi")
    assert res_wheat["sum_insured"] == 80000.0
    assert res_wheat["farmer_rate_percent"] == 1.5
    assert res_wheat["farmer_premium"] == 1200.0

    # Scenario D: Annual Commercial Cotton (5.0% statutory cap)
    res_cotton = pmfby_premium(scale_of_finance=60000, area=1.0, crop="cotton")
    assert res_cotton["sum_insured"] == 60000.0
    assert res_cotton["farmer_rate_percent"] == 5.0
    assert res_cotton["farmer_premium"] == 3000.0


# ---------------------------------------------------------------------------
# 2. Input validation: booleans, NaN, Inf, zero/negative, missing evidence
# ---------------------------------------------------------------------------
def test_pmfby_premium_input_validation():
    # Reject boolean scale of finance
    with pytest.raises(ValueError, match="must be a number, not a boolean"):
        pmfby_premium(scale_of_finance=True, area=1.0, crop="soybean")

    # Reject boolean area
    with pytest.raises(ValueError, match="must be a number, not a boolean"):
        pmfby_premium(scale_of_finance=50000, area=False, crop="soybean")

    # Reject NaN
    with pytest.raises(ValueError, match="cannot be NaN or infinity"):
        pmfby_premium(scale_of_finance=float("nan"), area=1.0, crop="soybean")

    # Reject Infinity
    with pytest.raises(ValueError, match="cannot be NaN or infinity"):
        pmfby_premium(scale_of_finance=50000, area=float("inf"), crop="soybean")

    # Reject zero / negative area
    with pytest.raises(ValueError, match="must be greater than zero"):
        pmfby_premium(scale_of_finance=50000, area=0, crop="soybean")

    with pytest.raises(ValueError, match="must be greater than zero"):
        pmfby_premium(scale_of_finance=50000, area=-1.5, crop="soybean")

    # Reject missing crop
    with pytest.raises(ValueError, match="Crop name is required"):
        pmfby_premium(scale_of_finance=50000, area=1.0, crop=None)

    # Reject unknown crop without verifiable rate evidence
    with pytest.raises(ValueError, match="not found in official PMFBY records"):
        pmfby_premium(scale_of_finance=50000, area=1.0, crop="dragonfruit_exotic")


# ---------------------------------------------------------------------------
# 3. Acres to hectares conversion & unit rejection
# ---------------------------------------------------------------------------
def test_acres_to_hectares_conversion():
    # 2.47105 acres should convert to 1.0 ha
    res_acres = pmfby_premium(
        scale_of_finance=50000, area=2.47105, unit="acres", crop="soybean"
    )
    assert abs(res_acres["area_ha"] - 1.0) < 0.01
    assert res_acres["sum_insured"] == 50000.0

    # Reject unsupported area units
    with pytest.raises(ValueError, match="Unsupported area unit 'bigha'"):
        pmfby_premium(scale_of_finance=50000, area=2.0, unit="bigha", crop="soybean")


# ---------------------------------------------------------------------------
# 4. Deadline checking: relative parsing, fixed clock, expired, and invalid dates
# ---------------------------------------------------------------------------
def test_claim_deadline_checking():
    # Relative timestamp 'yesterday at 9 pm' evaluated at 2026-11-17 12:00:00 IST
    # Loss: 2026-11-16 21:00:00 -> Deadline: 2026-11-19 21:00:00 (57.0 hours remaining)
    res_rel = pmfby_claim_deadline_check("yesterday at 9 pm", window_hours=72, now=FIXED_NOW)
    assert res_rel["loss_timestamp"].startswith("2026-11-16T21:00:00")
    assert res_rel["deadline_timestamp"].startswith("2026-11-19T21:00:00")
    assert res_rel["remaining_hours"] == 57.0
    assert res_rel["is_expired"] is False
    assert len(res_rel["reporting_channels"]) >= 4

    # Explicit ISO timestamp
    res_iso = pmfby_claim_deadline_check("2026-11-15 12:00:00", window_hours=72, now=FIXED_NOW)
    assert res_iso["remaining_hours"] == 24.0
    assert res_iso["is_expired"] is False

    # Expired timestamp
    res_exp = pmfby_claim_deadline_check("2026-11-10 10:00:00", window_hours=72, now=FIXED_NOW)
    assert res_exp["remaining_hours"] < 0
    assert res_exp["is_expired"] is True

    # Reject invalid / unparseable timestamp
    with pytest.raises(ValueError, match="Invalid loss timestamp"):
        pmfby_claim_deadline_check("not-a-real-date", now=FIXED_NOW)

    # Reject empty timestamp
    with pytest.raises(ValueError, match="Loss date/time is required"):
        pmfby_claim_deadline_check("", now=FIXED_NOW)


# ---------------------------------------------------------------------------
# 5. Hand-written agent: truthful traces, missing inputs, and strict refusal
# ---------------------------------------------------------------------------
def test_handwritten_agent_behavior():
    # A. Compound Question (Q4 with fixed clock)
    q4 = (
        "Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. "
        "By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?"
    )
    res4 = run_agent_loop(q4, clock_now=FIXED_NOW)
    assert "pmfby_premium" in res4["tools_called"]
    assert "pmfby_claim_deadline_check" in res4["tools_called"]
    assert "pmfby_knowledge_search" in res4["tools_called"]
    assert "1,176.00" in res4["answer"]
    assert "57.0 hours remaining" in res4["answer"]
    assert "Crop Insurance App" in res4["answer"]

    # B. Missing input handling (asking for premium without crop)
    res_miss = run_agent_loop("Calculate my premium for 2 ha with scale of finance Rs 50,000")
    assert "pmfby_premium" not in res_miss["tools_called"]
    assert "crop name" in res_miss["answer"].lower()

    # C. Strict Refusal on Personal Claim Status (Q6 & Q15)
    res_q6 = run_agent_loop("Has my PMFBY claim for kharif 2025 been approved?")
    assert "i don't know" in res_q6["answer"].lower()
    assert res_q6["confidence"] == 0.0
    assert res_q6["tools_called"] == []

    res_q15 = run_agent_loop("Can you check if my payment has reached my State Bank of India account?")
    assert "i don't know" in res_q15["answer"].lower()
    assert res_q15["tools_called"] == []


# ---------------------------------------------------------------------------
# 6. LangGraph agent: approval pause, resume, rejection, cancellation, replay protection
# ---------------------------------------------------------------------------
def test_langgraph_agent_approval_and_memory():
    sess_id = "test_langgraph_lifecycle_session_99"

    # Step 1: Request new calculation -> Must pause for approval
    q_calc = "Calculate premium for 1.2 ha soybean with scale of finance Rs 49,000"
    turn1 = run_langgraph_agent(query=q_calc, thread_id=sess_id)
    assert turn1["status"] == "approval_required"
    assert turn1["requires_approval"] is True
    assert "Approval Required" in turn1["answer"]

    # Step 2: User confirms approval (approved=True) on same session -> Executes and completes
    calc_id1 = turn1["pending_calculation"]["id"]
    turn2 = run_langgraph_agent(thread_id=sess_id, approved=True, calculation_id=calc_id1)
    assert turn2["status"] == "completed"
    assert turn2["requires_approval"] is False
    assert "1,176.00" in turn2["answer"]

    # Step 3: Replay protection: Attempting to approve again on completed session -> Rejected
    turn3 = run_langgraph_agent(thread_id=sess_id, approved=True, calculation_id=calc_id1)
    assert turn3["status"] == "rejected"
    assert "No pending calculation" in turn3["answer"]

    # Step 4: Submit a second calculation -> Approval is RESET for new calculation
    q_calc2 = "Calculate premium for 2.0 ha wheat with scale of finance Rs 40,000"
    turn4 = run_langgraph_agent(query=q_calc2, thread_id=sess_id)
    assert turn4["status"] == "approval_required"
    assert turn4["requires_approval"] is True
    calc_id2 = turn4["pending_calculation"]["id"]

    # Step 5: User cancels calculation (approved=False) -> Cancelled without executing tools
    turn5 = run_langgraph_agent(thread_id=sess_id, approved=False, calculation_id=calc_id2)
    assert turn5["status"] == "cancelled"
    assert turn5["requires_approval"] is False
    assert turn5["tool_calls"] == []
    assert "cancelled" in turn5["answer"].lower()

    # Step 6: Subsequent knowledge query on same session does NOT reuse old calculation params
    turn6 = run_langgraph_agent(
        query="What is the claim intimation timeline for localized calamities?",
        thread_id=sess_id,
    )
    assert turn6["status"] == "completed"
    assert turn6["requires_approval"] is False
    assert len(turn6["answer"]) > 20
    # Confirm knowledge search tool ran and no premium calculation tool was executed
    assert any(tc.get("tool") == "pmfby_knowledge_search" for tc in turn6["tool_calls"])
    assert not any(tc.get("tool") == "pmfby_premium" for tc in turn6["tool_calls"])


# ---------------------------------------------------------------------------
# 7. Session Isolation: Conversation IDs remain completely separate
# ---------------------------------------------------------------------------
def test_conversation_isolation():
    session_alpha = "isolated_session_alpha"
    session_beta = "isolated_session_beta"

    # Start pending calculation on session Alpha
    res_a1 = run_langgraph_agent(
        query="Calculate premium for 1.2 ha soybean at scale of finance Rs 49,000",
        thread_id=session_alpha,
    )
    assert res_a1["status"] == "approval_required"

    calc_a_id = res_a1["pending_calculation"]["id"]

    # Attempt to approve on session Beta -> Must be rejected (no pending calculation on Beta)
    res_b1 = run_langgraph_agent(thread_id=session_beta, approved=True, calculation_id=calc_a_id)
    assert res_b1["status"] == "rejected"
    assert "No pending calculation" in res_b1["answer"]

    # Session Alpha can still be approved independently
    res_a2 = run_langgraph_agent(thread_id=session_alpha, approved=True, calculation_id=calc_a_id)
    assert res_a2["status"] == "completed"
    assert "1,176.00" in res_a2["answer"]


# ---------------------------------------------------------------------------
# 8. API Endpoint POST /agent: validations, error handling, and end-to-end flow
# ---------------------------------------------------------------------------
def test_api_agent_endpoint_validations_and_flow():
    # 1. Empty query rejection
    res_empty = client.post("/agent", json={"query": "", "agent_type": "handwritten"})
    assert res_empty.status_code == 400

    # 2. Whitespace-only query rejection
    res_ws = client.post("/agent", json={"query": "   ", "agent_type": "langgraph"})
    assert res_ws.status_code == 400

    # 3. Neither query nor approved rejection
    res_none = client.post("/agent", json={})
    assert res_none.status_code == 400

    # 4. Resume without thread_id rejection
    res_no_tid = client.post("/agent", json={"approved": True})
    assert res_no_tid.status_code == 400

    # 5. Full LangGraph approval flow via API
    api_thread = "api_e2e_approval_session_42"
    r_turn1 = client.post(
        "/agent",
        json={
            "query": "Calculate premium for 1.2 ha soybean at scale of finance Rs 49,000",
            "thread_id": api_thread,
            "agent_type": "langgraph",
        },
    )
    assert r_turn1.status_code == 200
    b1 = r_turn1.json()
    assert b1["status"] == "approval_required"
    assert b1["requires_approval"] is True

    calc_id = b1["pending_calculation"]["id"]
    r_turn2 = client.post(
        "/agent",
        json={
            "thread_id": api_thread,
            "approved": True,
            "calculation_id": calc_id,
            "agent_type": "langgraph",
        },
    )
    assert r_turn2.status_code == 200
    b2 = r_turn2.json()
    assert b2["status"] == "completed"
    assert b2["requires_approval"] is False
    assert "1,176.00" in b2["answer"]
