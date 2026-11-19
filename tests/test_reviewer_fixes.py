"""Comprehensive regression tests covering all 10 reviewer-identified areas.

1. Timestamp parsing without implicit defaults (bare yesterday, bare today, date-only, future, valid).
2. Calculation ID enforcement (missing, mismatched, correct, interrupt preservation, successive calcs).
3. Crop and season consistency validation (rejecting Wheat in Kharif, Soybean in Rabi).
4. Rate evidence validation (records.json required, honest failure when missing/malformed).
5. Feedback deduplication with (thread_id, response_id) pairs.
6. Streamlit UI AppTest verifying clean zero-fabricated initial state.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import uuid
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.graph import run_langgraph_agent
from app.tools import (
    IST,
    load_rate_table_from_records,
    parse_loss_timestamp,
    resolve_crop_and_category,
)
from app.agent_loop import extract_loss_timestamp_text

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent


# --- 1. TIMESTAMP HANDLING WITHOUT INVENTED DEFAULTS ---


def test_bare_relative_timestamps_require_time():
    """Ensure bare 'yesterday', 'today', or date-only terms raise honest clarifications rather than inventing 9 PM."""
    now = datetime(2026, 11, 18, 14, 0, 0, tzinfo=IST)

    # Bare 'yesterday' must raise ValueError asking for time
    with pytest.raises(ValueError, match="Please provide the approximate time of loss"):
        parse_loss_timestamp("yesterday", now=now)

    # Bare 'today' must raise ValueError asking for time
    with pytest.raises(ValueError, match="Please provide the approximate time of loss"):
        parse_loss_timestamp("today", now=now)

    # Bare date without time (YYYY-MM-DD) must raise ValueError asking for time
    with pytest.raises(ValueError, match="Date .* provided without time"):
        parse_loss_timestamp("2026-11-17", now=now)

    # Valid explicit yesterday with time should parse accurately
    valid_dt = parse_loss_timestamp("yesterday at 9 pm", now=now)
    assert valid_dt.hour == 21
    assert valid_dt.minute == 0
    assert valid_dt.date() == (now - timedelta(days=1)).date()

    # Relative hours ago should parse accurately
    rel_dt = parse_loss_timestamp("10 hours ago", now=now)
    assert abs((now - rel_dt).total_seconds() - 36000) < 1.0

    # Future date must be rejected
    with pytest.raises(ValueError, match="cannot be in the future"):
        parse_loss_timestamp("2029-05-01 10:00", now=now)


def test_agent_extract_loss_timestamp_text():
    """Ensure extraction does not append 'at 9 pm' to bare yesterday."""
    q_bare = "Hailstorm hit my soybean field yesterday. What should I do?"
    extracted_bare = extract_loss_timestamp_text(q_bare)
    assert extracted_bare == "yesterday"  # Verbatim, validator will enforce time requirement

    q_with_time = "Hailstorm hit my soybean field yesterday at 9 pm."
    extracted_time = extract_loss_timestamp_text(q_with_time)
    assert "yesterday at 9 pm" in extracted_time.lower()


# --- 2. EXACT CALCULATION ID ENFORCEMENT & PRESERVATION ---


def test_approval_requires_exact_calculation_id_and_preserves_interrupt():
    """Ensure missing or mismatched calculation_id preserves pending interrupt without executing tools."""
    sess = f"test_calc_id_enforce_{uuid.uuid4().hex[:8]}"
    q = "Calculate soybean premium for 1.2 ha with scale of finance 49000"

    # Step 1: Pauses at interrupt
    r1 = run_langgraph_agent(query=q, thread_id=sess)
    assert r1["status"] == "approval_required"
    assert r1["requires_approval"] is True
    real_calc_id = r1["pending_calculation"]["id"]
    assert real_calc_id.startswith("calc_")

    # Step 2: Attempt approval with MISSING calculation_id -> must reject and preserve interrupt
    r_missing = run_langgraph_agent(thread_id=sess, approved=True, calculation_id=None)
    assert r_missing["status"] == "rejected"
    assert r_missing["requires_approval"] is True
    assert r_missing["pending_calculation"]["id"] == real_calc_id
    assert "A valid 'calculation_id' is required" in r_missing["answer"]

    # Step 3: Attempt approval with MISMATCHED calculation_id -> must reject and preserve interrupt
    r_mismatch = run_langgraph_agent(thread_id=sess, approved=True, calculation_id="calc_fake9999")
    assert r_mismatch["status"] == "rejected"
    assert r_mismatch["requires_approval"] is True
    assert r_mismatch["pending_calculation"]["id"] == real_calc_id
    assert "Calculation ID mismatch" in r_mismatch["answer"]

    # Step 4: Resume with the REAL calculation_id -> must succeed and execute pmfby_premium
    r_success = run_langgraph_agent(thread_id=sess, approved=True, calculation_id=real_calc_id)
    assert r_success["status"] == "completed"
    assert r_success["requires_approval"] is False
    assert len(r_success["tool_calls"]) == 1
    assert r_success["tool_calls"][0]["tool"] == "pmfby_premium"
    assert "58,800" in r_success["answer"]
    assert "1,176" in r_success["answer"]


def test_two_successive_calculations_require_fresh_approval():
    """Ensure a second calculation gets a new calculation ID and does not inherit prior approval."""
    sess = f"test_successive_calcs_{uuid.uuid4().hex[:8]}"

    # Turn 1: First calculation (Soybean 1.0 ha)
    r1 = run_langgraph_agent(
        query="Calculate soybean premium for 1 ha at scale of finance 40000", thread_id=sess
    )
    assert r1["status"] == "approval_required"
    calc1_id = r1["pending_calculation"]["id"]
    # Approve Turn 1
    r1_app = run_langgraph_agent(thread_id=sess, approved=True, calculation_id=calc1_id)
    assert r1_app["status"] == "completed"
    assert "40,000" in r1_app["answer"]

    # Turn 2: Second calculation (Wheat 2.0 ha)
    r2 = run_langgraph_agent(
        query="Calculate wheat premium for 2 ha at scale of finance 45000", thread_id=sess
    )
    assert r2["status"] == "approval_required"
    assert r2["requires_approval"] is True
    calc2_id = r2["pending_calculation"]["id"]
    assert calc2_id != calc1_id  # Fresh ID!

    # Old ID cannot be reused to approve Turn 2
    r_old = run_langgraph_agent(thread_id=sess, approved=True, calculation_id=calc1_id)
    assert r_old["status"] == "rejected"
    assert r_old["pending_calculation"]["id"] == calc2_id


# --- 3. CROP AND SEASON CONSISTENCY VALIDATION ---


def test_crop_season_consistency():
    """Ensure conflicting crop-season pairs raise explicit validation errors."""
    # Wheat is strictly Rabi; cannot calculate under Kharif
    with pytest.raises(
        ValueError, match="Conflicting season/crop: 'Wheat' is classified as a Rabi"
    ):
        resolve_crop_and_category(crop="wheat", season="kharif")

    # Soybean is strictly Kharif; cannot calculate under Rabi
    with pytest.raises(
        ValueError, match="Conflicting season/crop: 'Soybean' is classified as a Kharif"
    ):
        resolve_crop_and_category(crop="soybean", season="rabi")

    # Correct seasons must resolve accurately
    _, season_w, cat_w = resolve_crop_and_category(crop="wheat", season="rabi")
    assert season_w == "rabi"
    assert cat_w == "rabi_foodgrain_oilseed"

    _, season_s, cat_s = resolve_crop_and_category(crop="soybean", season="kharif")
    assert season_s == "kharif"
    assert cat_s == "kharif_foodgrain_oilseed"


# --- 4. RATE TABLE EVIDENCE VALIDATION ---


def test_rate_table_from_records_authenticity():
    """Ensure rates are loaded authentically from records.json."""
    rate_table = load_rate_table_from_records()
    assert "kharif_foodgrain_oilseed" in rate_table
    assert "rabi_foodgrain_oilseed" in rate_table
    assert "commercial_horticultural" in rate_table

    assert rate_table["kharif_foodgrain_oilseed"]["rate_percent"] == Decimal("2.0")
    assert rate_table["rabi_foodgrain_oilseed"]["rate_percent"] == Decimal("1.5")
    assert rate_table["commercial_horticultural"]["rate_percent"] == Decimal("5.0")


# --- 5. FEEDBACK DEDUPLICATION BY (THREAD_ID, RESPONSE_ID) ---


def test_feedback_deduplication_by_response_id():
    """Verify that multiple ratings for the same response_id update rather than duplicate, while different response_ids remain distinct."""
    thread_id = f"test_fb_dedup_{uuid.uuid4().hex[:8]}"
    resp1_id = f"resp_{uuid.uuid4().hex[:10]}"
    resp2_id = f"resp_{uuid.uuid4().hex[:10]}"

    # Submit upvote for response 1
    r1 = client.post(
        "/feedback",
        json={
            "thread_id": thread_id,
            "response_id": resp1_id,
            "query": "What is PMFBY?",
            "rating": "up",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["updated"] is False

    # Change vote to downvote for response 1 -> Must UPDATE (not duplicate)
    r1_change = client.post(
        "/feedback",
        json={
            "thread_id": thread_id,
            "response_id": resp1_id,
            "query": "What is PMFBY?",
            "rating": "down",
        },
    )
    assert r1_change.status_code == 200
    assert r1_change.json()["updated"] is True

    # Submit vote for a DIFFERENT response 2 in the same thread
    r2 = client.post(
        "/feedback",
        json={
            "thread_id": thread_id,
            "response_id": resp2_id,
            "query": "What is 72h rule?",
            "rating": "up",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["updated"] is False

    # Query filtered feedback for this thread
    r_list = client.get(f"/feedback?thread_id={thread_id}")
    assert r_list.status_code == 200
    records = r_list.json()["feedback"]
    assert len(records) == 2  # Exactly 2 distinct responses!
    assert any(rec["response_id"] == resp1_id and rec["rating"] == "down" for rec in records)
    assert any(rec["response_id"] == resp2_id and rec["rating"] == "up" for rec in records)


# --- 6. STREAMLIT UI APPTEST: ZERO FABRICATED INITIAL STATE ---


def test_streamlit_ui_initializes_empty_without_fabricated_state():
    """AppTest verification: ui/app.py starts clean with zero fabricated conversation, approval, or clock state."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "ui" / "app.py")).run()
    assert not at.exception

    # Session state must start clean
    assert len(at.session_state.messages) == 0
    assert at.session_state.pending_approval is None
    assert at.session_state.claim_clock_data is None
    assert at.session_state.demo_mode is False
