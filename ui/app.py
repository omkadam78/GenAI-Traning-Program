"""Streamlit Web UI for FasalBima Sathi (Day 10).

Features:
1. Multi-turn chat interface with memory and thread isolation
2. Native LangGraph human-in-the-loop approval card bound to exact calculation IDs
3. Live 72-Hour Calamity Intimation Clock with automatic countdown and official reporting channels
4. Transparent tool execution traces and genuine guideline citations
5. Thumbs-up / Thumbs-down feedback collection keyed by response_id with safe persistence
6. Strict HTTP backend communication preventing silent local fallbacks and duplicate executions
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
import uuid
import zoneinfo
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = Path(__file__).resolve().parent

# Ensure project root is first in sys.path and remove UI directory from sys.path to prevent 'ui/app.py' collision
while str(UI_DIR) in sys.path:
    sys.path.remove(str(UI_DIR))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

from app.tools import IST

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="FasalBima Sathi - PMFBY AI Assistant",
    page_icon="🌾",
    layout="wide",
)


def is_api_alive() -> bool:
    """Check if the FastAPI backend is running."""
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def save_feedback_entry(
    thread_id: str,
    response_id: str,
    query: str,
    rating: str,
    comment: str | None = None,
) -> bool:
    """Submit user feedback to backend /feedback endpoint."""
    try:
        r = requests.post(
            f"{API_BASE_URL}/feedback",
            json={
                "thread_id": thread_id,
                "response_id": response_id,
                "query": query,
                "rating": rating,
                "comment": comment,
            },
            timeout=3.0,
        )
        if r.status_code == 200:
            return True
        st.error(f"Feedback submission failed ({r.status_code}): {r.text}")
        return False
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot submit feedback: FastAPI backend at {API_BASE_URL} is unreachable.")
        return False
    except Exception as err:
        st.error(f"Feedback error: {err}")
        return False


def call_agent_api(
    query: str | None = None,
    thread_id: str | None = None,
    approved: bool | None = None,
    calculation_id: str | None = None,
    agent_type: str = "langgraph",
    execution_mode: str = "backend",
) -> tuple[dict | None, str | None]:
    """Execute agent turn via HTTP backend or explicit offline fallback.
    
    Returns (result_dict, error_message). Prevents silent local execution on error.
    """
    if execution_mode == "offline":
        try:
            if agent_type == "handwritten":
                from app.agent_loop import run_agent_loop
                res = run_agent_loop(query or "")
                res["thread_id"] = thread_id or f"session_{uuid.uuid4().hex[:12]}"
                res["agent_type"] = "handwritten"
                return res, None
            else:
                from app.graph import run_langgraph_agent
                res = run_langgraph_agent(
                    query=query,
                    thread_id=thread_id,
                    approved=approved,
                    calculation_id=calculation_id,
                )
                res["agent_type"] = "langgraph"
                return res, None
        except Exception as err:
            return None, f"Local offline execution error: {err}"

    # Production Mode: Strict HTTP Backend Execution with Idempotency
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    payload = {
        "query": query,
        "thread_id": thread_id,
        "approved": approved,
        "calculation_id": calculation_id,
        "agent_type": agent_type,
        "request_id": req_id,
    }
    try:
        res = requests.post(f"{API_BASE_URL}/agent", json=payload, timeout=30.0)
        if res.status_code == 200:
            return res.json(), None
        try:
            detail = res.json().get("detail", res.text)
        except Exception:
            detail = res.text
        return None, f"Backend Error ({res.status_code}): {detail}"
    except requests.exceptions.ConnectionError:
        return None, (
            f"Backend Connection Error: FastAPI server is not reachable at {API_BASE_URL}. "
            "Please ensure the backend is running (`uvicorn app.main:app --port 8000`)."
        )
    except requests.exceptions.Timeout:
        return None, (
            "Backend Request Timeout: The agent request timed out after 30 seconds. "
            "To prevent duplicate execution, this request was not rerun locally. Please retry."
        )
    except Exception as err:
        return None, f"Request failed: {err}"


# --- INITIALIZE EMPTY STATE (Zero Fabricated State) ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"session_{uuid.uuid4().hex[:12]}"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None

if "claim_clock_data" not in st.session_state:
    st.session_state.claim_clock_data = None

if "feedback_status" not in st.session_state:
    st.session_state.feedback_status = {}

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = False


# --- SIDEBAR: Controls & Live 72-Hour Calamity Clock ---
with st.sidebar:
    st.title("🌾 FasalBima Sathi")
    st.markdown(
        "**PMFBY Decision Support System**\n\n"
        "Grounded on Revamped Operational Guidelines (Kharif 2020 onwards)."
    )

    st.divider()

    st.subheader("⚙️ Session Controls")
    st.caption(f"Session ID: `{st.session_state.thread_id}`")

    agent_mode = st.radio(
        "Agent Engine:",
        ["LangGraph (Stateful + Interrupt)", "Handwritten ReAct"],
        index=0,
    )
    agent_key = "langgraph" if "LangGraph" in agent_mode else "handwritten"

    exec_mode = st.radio(
        "Execution Mode:",
        ["HTTP Backend (Production)", "Offline Direct (Demo)"],
        index=0,
        help="Production mode calls the FastAPI service with idempotency; Offline mode runs locally in-process.",
    )
    exec_mode_val = "backend" if "HTTP Backend" in exec_mode else "offline"

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Reset", use_container_width=True, help="Clear session and start fresh"):
            st.session_state.thread_id = f"session_{uuid.uuid4().hex[:12]}"
            st.session_state.messages = []
            st.session_state.pending_approval = None
            st.session_state.claim_clock_data = None
            st.session_state.feedback_status = {}
            st.session_state.demo_mode = False
            st.rerun()

    with col_btn2:
        if st.button("📌 Demo", use_container_width=True, help="Opt-in sample scenario"):
            st.session_state.thread_id = f"demo_{uuid.uuid4().hex[:8]}"
            st.session_state.demo_mode = True
            st.session_state.messages = [
                {
                    "role": "user",
                    "content": "Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?",
                },
                {
                    "role": "assistant",
                    "response_id": f"resp_{uuid.uuid4().hex[:10]}",
                    "content": (
                        "[OPT-IN DEMO SAMPLE DATA]\n\n"
                        "**Localized Calamity Intimation (72-Hour Rule):**\n"
                        "- **Statutory Window:** Must be intimated within **72 hours** of loss occurrence.\n"
                        "- **Loss Event:** Yesterday at 9:00 PM IST\n"
                        "- **Intimation Deadline:** **Within 72 Hours** (57.0 hours remaining)\n"
                        "- **Authorized Reporting Channels:** Crop Insurance App (NCIP), Krishi Rakshak Helpline (14447), Bank Branch / PACS, or Local Agriculture Officer\n"
                        "- *Governing Rule:* Revamped OG (Kharif 2020 onwards), Para 15.1.2 & 15.2.2\n\n"
                        "**PMFBY Premium Calculation (Confirmed):**\n"
                        "- **Sum Insured:** ₹58,800.00 (Scale of Finance: ₹49,000.00/ha × 1.20 ha)\n"
                        "- **Farmer Premium Rate:** 2.00% (Kharif Soybean)\n"
                        "- **Estimated Maximum Farmer Premium Share:** **₹1,176.00**\n"
                        "- *Rate Basis:* Estimated maximum farmer premium (capped at 2.0% statutory ceiling under PMFBY Para 13.1 Table 1)\n"
                        "- *Governing Rule:* Kharif Foodgrain & Oilseed Premium Cap (Revamped OG, Para 13.1)"
                    ),
                    "steps": [
                        "Identified loss event: 'yesterday at 9 pm'. Executed pmfby_claim_deadline_check.",
                        "Identified calculation parameters: Soybean, 1.2 ha, SOF ₹49,000/ha. Received user approval.",
                        "Tool executed: pmfby_premium -> Sum Insured: ₹58,800.00, Farmer Share: ₹1,176.00.",
                    ],
                    "tool_calls": [
                        {
                            "tool": "pmfby_claim_deadline_check",
                            "input": {"loss_timestamp": "yesterday at 9 pm", "window_hours": 72},
                            "output": {"remaining_hours": 57.0, "is_expired": False, "reporting_channels": ["Crop Insurance App", "14447 Helpline", "Bank Branch"]},
                        },
                        {
                            "tool": "pmfby_premium",
                            "input": {"crop": "soybean", "season": "kharif", "area": 1.2, "area_unit": "ha", "scale_of_finance": 49000.0, "scale_of_finance_unit": "per_ha"},
                            "output": {"sum_insured": 58800.0, "farmer_rate_percent": 2.0, "farmer_premium": 1176.0, "is_estimated_maximum": True},
                        },
                    ],
                    "citations": [
                        {
                            "source": "revamped_ogs_final.pdf",
                            "page": 13,
                            "title": "Statutory Farmer Premium Rates (Para 13.1 Table 1)",
                            "score": 0.94,
                        },
                        {
                            "source": "revamped_ogs_final.pdf",
                            "page": 73,
                            "title": "Localized Calamities 72-Hour Intimation (Para 15.1.2)",
                            "score": 0.91,
                        },
                    ],
                    "query": "Hailstorm hit my 1.2 ha soybean at 9 pm yesterday...",
                    "disclaimer": "Information from official PMFBY guidelines, not insurance or legal advice. Claim decisions rest with the insurance company and the state government.",
                },
            ]
            st.session_state.pending_approval = None
            st.session_state.claim_clock_data = {
                "loss_timestamp": (datetime.now(tz=IST) - timedelta(hours=15)).strftime("%Y-%m-%d %H:%M:%S IST"),
                "deadline_timestamp": (datetime.now(tz=IST) + timedelta(hours=57)).strftime("%Y-%m-%d %H:%M:%S IST"),
                "window_hours": 72,
                "remaining_hours": 57.0,
                "is_expired": False,
                "reporting_channels": [
                    "Crop Insurance App (National Crop Insurance Portal)",
                    "Krishi Rakshak Helpline: 14447",
                    "Bank Branch / PACS where premium was debited",
                    "Local Agriculture Officer / Revenue Authority",
                ],
            }
            st.rerun()

    st.divider()

    # Signature Feature: Live 72-Hour Calamity Intimation Clock
    st.subheader("⏱️ 72-Hour Calamity Clock")
    st.markdown(
        "**Localized Calamity & Post-Harvest Losses**\n"
        "Must be reported within **72 hours** of occurrence (PMFBY Paras 15.1.2 & 15.2.2)."
    )

    loss_date = st.date_input("Loss Event Date:", value=datetime.now(tz=IST).date(), key="sidebar_loss_date")
    loss_time_val = st.time_input("Approximate Loss Time:", value=time(10, 0), key="sidebar_loss_time")

    if st.button("Check Intimation Deadline", use_container_width=True):
        loss_dt = datetime.combine(loss_date, loss_time_val, tzinfo=IST)
        now_dt = datetime.now(tz=IST)

        if loss_dt > now_dt:
            st.error("Loss event time cannot be in the future.")
        else:
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/claim-clock",
                    json={
                        "loss_timestamp": loss_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "window_hours": 72,
                    },
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    st.session_state.claim_clock_data = resp.json()
                else:
                    try:
                        err_det = resp.json().get("detail", resp.text)
                    except Exception:
                        err_det = resp.text
                    st.error(f"❌ Backend Clock Error ({resp.status_code}): {err_det}")
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Backend Connection Error: FastAPI service at {API_BASE_URL} is unreachable.")
            except Exception as e:
                st.error(f"❌ Clock request failed: {e}")

    # Live Countdown Fragment (Updates every 5 seconds without whole page reload)
    @st.fragment(run_every="5s")
    def render_live_clock():
        if not st.session_state.get("claim_clock_data"):
            return

        ck = st.session_state.claim_clock_data
        deadline_str = ck.get("deadline_timestamp", "")
        dt_clean = deadline_str.replace(" IST", "").strip()
        deadline_dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                deadline_dt = datetime.strptime(dt_clean, fmt).replace(tzinfo=IST)
                break
            except Exception:
                pass

        now_dt = datetime.now(tz=IST)
        if deadline_dt:
            rem_sec = (deadline_dt - now_dt).total_seconds()
            if rem_sec <= 0:
                elapsed_hrs = abs(rem_sec) / 3600.0
                st.error(f"🚨 **Deadline Expired** ({elapsed_hrs:.1f} hrs ago)")
            else:
                rem_h = int(rem_sec // 3600)
                rem_m = int((rem_sec % 3600) // 60)
                rem_s = int(rem_sec % 60)
                st.success(f"⏳ **{rem_h}h {rem_m}m {rem_s}s Remaining** (Live Countdown)")
        else:
            if ck.get("is_expired"):
                st.error(f"🚨 **Deadline Expired** ({abs(ck.get('remaining_hours', 0))} hrs ago)")
            else:
                st.success(f"⏳ **{ck.get('remaining_hours')} Hours Remaining**")

        st.markdown(f"**Loss Event:** `{ck.get('loss_timestamp')}`")
        st.markdown(f"**Deadline:** `{ck.get('deadline_timestamp')}`")

        with st.expander("📞 Authorized Reporting Channels", expanded=True):
            for ch in ck.get("reporting_channels", []):
                st.markdown(f"- {ch}")
        st.caption("⚠️ Note: This tool computes the statutory deadline; it does not submit a claim.")

    render_live_clock()


# --- MAIN AREA ---
st.title("🌾 FasalBima Sathi - PMFBY AI Assistant")
st.info(
    "ℹ️ **Official Guidance**: Answers are grounded on the PMFBY Revamped Operational Guidelines. "
    "This system provides rule lookups, arithmetic premium estimates, and calamity deadline checks. "
    "It does not access private bank accounts or file claims."
)

if exec_mode_val == "offline":
    st.warning("⚠️ Running in Offline Direct Execution mode. Switches to in-process execution.")

if st.session_state.demo_mode:
    st.info("📌 **Demo Mode Active**: Viewing sample interaction data. Click **Reset** in sidebar to return to a clean session.")

# Welcome card when no messages exist yet
if not st.session_state.messages:
    with st.container(border=True):
        st.markdown("### 👋 Welcome to FasalBima Sathi")
        st.markdown(
            "An AI decision-support assistant grounded exclusively on the **PMFBY Revamped Operational Guidelines**.\n\n"
            "**What you can do:**\n"
            "- **Ask PMFBY Guidelines**: Inquire about coverage, exclusions, crop loss definitions, and the 72-hour reporting rule.\n"
            "- **Calculate Crop Premium**: Request premium calculations for your crop, area, and Scale of Finance with transparent human-in-the-loop approval.\n"
            "- **Check Calamity Deadlines**: Enter localized loss events to track intimation windows with the live 72-hour intimation clock.\n\n"
            "*Try asking:* `Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?`"
        )

# Display Chat History
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Tool Traces
        if msg.get("tool_calls") or msg.get("steps"):
            with st.expander("🔍 Reasoning Steps & Tool Executions"):
                if msg.get("steps"):
                    st.markdown("**Execution Steps:**")
                    for s in msg["steps"]:
                        st.markdown(f"- `{s}`")
                if msg.get("tool_calls"):
                    st.markdown("**Executed Tools:**")
                    for tc in msg["tool_calls"]:
                        st.json(tc)

        # Citations
        if msg.get("citations"):
            with st.expander("📚 Official PMFBY Citations"):
                for cit in msg["citations"]:
                    st.markdown(
                        f"- **{cit.get('title', 'PMFBY Rule')}** (Page {cit.get('page', 1)})\n"
                        f"  *Source:* `{cit.get('source', 'Operational Guidelines')}` "
                        f"| *Relevance Score:* `{cit.get('score', cit.get('relevance_score', 0.8))}`"
                    )

        # Thumbs up / down feedback on assistant responses
        if msg["role"] == "assistant" and msg.get("response_id"):
            resp_id = msg["response_id"]
            cols = st.columns([1, 1, 8])
            with cols[0]:
                if st.button("👍", key=f"up_{resp_id}_{idx}", help="Helpful and accurate"):
                    if save_feedback_entry(st.session_state.thread_id, resp_id, msg.get("query", ""), "up"):
                        st.session_state.feedback_status[resp_id] = "up"
            with cols[1]:
                if st.button("👎", key=f"down_{resp_id}_{idx}", help="Inaccurate or incomplete"):
                    if save_feedback_entry(st.session_state.thread_id, resp_id, msg.get("query", ""), "down"):
                        st.session_state.feedback_status[resp_id] = "down"

            if resp_id in st.session_state.feedback_status:
                current_rating = st.session_state.feedback_status[resp_id]
                st.caption(f"Feedback recorded: {'👍 Thumbs Up' if current_rating == 'up' else '👎 Thumbs Down'}")


# --- PENDING APPROVAL CARD (Human-in-the-loop) ---
if st.session_state.pending_approval:
    pending = st.session_state.pending_approval
    calc_id = pending.get("id")
    params = pending.get("params", {})

    st.warning("⚠️ **Approval Required for Financial Calculation**")
    with st.container(border=True):
        st.markdown(f"### Calculation Approval: `{calc_id}`")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Crop:** {str(params.get('crop')).title()}")
            st.markdown(f"**Area:** {params.get('area')} {params.get('area_unit', 'ha')}")
        with col2:
            st.markdown(f"**Season:** {str(params.get('season') or 'Statutory').title()}")
            st.markdown(f"**Scale of Finance:** ₹{params.get('scale_of_finance', 0):,.2f}/{params.get('scale_of_finance_unit', 'per_ha')}")

        st.caption("PMFBY calculation uses statutory rates from records.json and pure arithmetic Decimal precision.")

        btn_cols = st.columns([2, 2, 6])
        with btn_cols[0]:
            if st.button("✅ Approve & Calculate", type="primary", use_container_width=True, key=f"btn_approve_{calc_id}"):
                res, err = call_agent_api(
                    thread_id=st.session_state.thread_id,
                    approved=True,
                    calculation_id=calc_id,
                    agent_type=agent_key,
                    execution_mode=exec_mode_val,
                )
                if err:
                    st.error(err)
                elif res:
                    st.session_state.pending_approval = None
                    st.session_state.messages.append({
                        "role": "assistant",
                        "response_id": res.get("response_id", f"resp_{uuid.uuid4().hex[:10]}"),
                        "content": res.get("answer", ""),
                        "steps": res.get("steps", []),
                        "tool_calls": res.get("tool_calls", []),
                        "citations": res.get("citations", []),
                        "query": f"Approval for {calc_id}",
                        "disclaimer": res.get("disclaimer"),
                    })
                    st.rerun()

        with btn_cols[1]:
            if st.button("❌ Cancel Calculation", type="secondary", use_container_width=True, key=f"btn_cancel_{calc_id}"):
                res, err = call_agent_api(
                    thread_id=st.session_state.thread_id,
                    approved=False,
                    calculation_id=calc_id,
                    agent_type=agent_key,
                    execution_mode=exec_mode_val,
                )
                if err:
                    st.error(err)
                elif res:
                    st.session_state.pending_approval = None
                    st.session_state.messages.append({
                        "role": "assistant",
                        "response_id": res.get("response_id", f"resp_{uuid.uuid4().hex[:10]}"),
                        "content": res.get("answer", "Calculation cancelled as requested."),
                        "steps": res.get("steps", []),
                        "tool_calls": [],
                        "citations": [],
                        "query": f"Cancel {calc_id}",
                        "disclaimer": res.get("disclaimer"),
                    })
                    st.rerun()


# --- CHAT INPUT ---
user_input = st.chat_input("Ask a PMFBY question, calculate premium, or check a calamity deadline...")
if user_input:
    # Append user question
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Call agent
    with st.spinner("Consulting PMFBY guidelines..."):
        agent_res, err = call_agent_api(
            query=user_input,
            thread_id=st.session_state.thread_id,
            agent_type=agent_key,
            execution_mode=exec_mode_val,
        )

    if err:
        st.error(err)
    elif agent_res:
        # Check if calculation approval is needed
        if agent_res.get("requires_approval") and agent_res.get("pending_calculation"):
            st.session_state.pending_approval = agent_res["pending_calculation"]

        st.session_state.messages.append({
            "role": "assistant",
            "response_id": agent_res.get("response_id", f"resp_{uuid.uuid4().hex[:10]}"),
            "content": agent_res.get("answer", ""),
            "steps": agent_res.get("steps", []),
            "tool_calls": agent_res.get("tool_calls", []),
            "citations": agent_res.get("citations", []),
            "query": user_input,
            "disclaimer": agent_res.get("disclaimer"),
        })
        st.rerun()
