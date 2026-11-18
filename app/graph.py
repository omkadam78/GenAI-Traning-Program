"""LangGraph agent for FasalBima Sathi with Memory and Approval Step (Days 9 & 10).

Rebuilds the PMFBY assistant into a stateful LangGraph workflow featuring:
1. Intent classification & RAG search
2. Pure arithmetic PMFBY premium tool integration with Decimal precision
3. Stateful conversation memory via LangGraph MemorySaver
4. Native LangGraph interrupt() and Command(resume=...) human-in-the-loop approval step
5. Strict parameter binding to immutable calculation ID, cancellation, and replay protection
6. Compound query handling answering every supported part (premium, deadline, channels)

Note on Memory:
Uses LangGraph MemorySaver for in-memory session checkpointing across conversation turns.
State is strictly isolated per conversation ID (thread_id). Note that in-memory checkpoints
persist across turns within the running process, but do not persist across server restarts.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict
import zoneinfo

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent_loop import (
    OUT_OF_SCOPE_PATTERNS,
    _is_out_of_scope,
    extract_loss_timestamp_text,
    extract_premium_params,
)
from app.tools import (
    IST,
    pmfby_claim_deadline_check,
    pmfby_knowledge_search,
    pmfby_premium,
)

DISCLAIMER = (
    "Information from official PMFBY guidelines, not insurance or legal advice. "
    "Claim decisions rest with the insurance company and the state government."
)


class AgentState(TypedDict, total=False):
    """LangGraph state representation for PMFBY agent."""
    thread_id: str
    query: str
    intent: str  # "refusal", "premium_calc", "knowledge_search", "compound", "clarification"
    pending_calculation: Optional[Dict[str, Any]]
    requires_approval: bool
    compound_deadline: Optional[Dict[str, Any]]
    deadline_clarification: Optional[str]
    tool_calls: List[Dict[str, Any]]
    steps: List[str]
    citations: List[Dict[str, Any]]
    status: str  # "completed", "approval_required", "cancelled", "rejected", "clarification_needed", "error"
    answer: str
    confidence: float


def classify_node(state: AgentState) -> Dict[str, Any]:
    """Classify farmer query intent and manage calculation / knowledge dispatch."""
    query = (state.get("query") or "").strip()
    thread_id = state.get("thread_id") or f"session_{uuid.uuid4().hex[:12]}"
    q_low = query.casefold()

    # Reset request-specific traces for fresh turn
    steps: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    # Case A: Out-of-scope check (Strict Q6 mandate)
    if _is_out_of_scope(query):
        steps.append("Classified query as out-of-scope personal claim/bank status -> Route to refusal")
        return {
            "thread_id": thread_id,
            "intent": "refusal",
            "requires_approval": False,
            "pending_calculation": None,
            "compound_deadline": None,
            "deadline_clarification": None,
            "steps": steps,
            "tool_calls": [],
            "citations": [],
        }

    # Check for deadline / calamity intimation in compound or standalone queries
    loss_ts_text = extract_loss_timestamp_text(query)
    compound_deadline: Optional[Dict[str, Any]] = None
    deadline_clarification: Optional[str] = None
    if loss_ts_text and any(t in q_low for t in ("hailstorm", "loss", "calamity", "inundation", "landslide", "inform", "deadline", "hours")):
        try:
            deadline_res = pmfby_claim_deadline_check(loss_timestamp=loss_ts_text, window_hours=72)
            tool_calls.append({
                "tool": "pmfby_claim_deadline_check",
                "input": {"loss_timestamp": loss_ts_text, "window_hours": 72},
                "output": deadline_res,
            })
            steps.append(
                f"Tool executed: pmfby_claim_deadline_check -> Deadline: {deadline_res['deadline_timestamp']}, "
                f"remaining: {deadline_res['remaining_hours']}h"
            )
            compound_deadline = deadline_res
        except ValueError as err:
            deadline_clarification = str(err)
            steps.append(f"Deadline clarification required: {err}")
        except Exception as err:
            steps.append(f"Deadline check skipped: {err}")

    # Case B: Check if calculation is intended
    calc_params = extract_premium_params(query)
    if calc_params["is_calc_intent"]:
        missing = []
        if not calc_params["crop"]:
            missing.append("crop name (e.g. soybean, wheat, cotton)")
        if calc_params["area"] is None:
            missing.append("area in hectares or acres")
        if calc_params["scale_of_finance"] is None:
            missing.append("scale of finance in ₹ per ha/acre")

        if missing:
            steps.append(f"Calculation requested but missing inputs: {missing} -> Route to clarification")
            clarification_msg = f"To calculate your PMFBY premium, please specify: {', '.join(missing)}."
            if compound_deadline:
                clarification_msg = (
                    f"**Localized Calamity Intimation (72-Hour Rule):**\n"
                    f"- **Statutory Window:** Must be intimated within **72 hours** of loss occurrence.\n"
                    f"- **Intimation Deadline:** {compound_deadline['deadline_timestamp']} "
                    f"({compound_deadline['remaining_hours']} hours remaining)\n"
                    f"- **Reporting Channels:** {', '.join(compound_deadline['reporting_channels'])}\n\n"
                    f"{clarification_msg}"
                )
            elif deadline_clarification:
                clarification_msg = (
                    f"**Localized Calamity Intimation (72-Hour Rule):**\n{deadline_clarification}\n\n"
                    f"{clarification_msg}"
                )
            return {
                "thread_id": thread_id,
                "intent": "clarification",
                "requires_approval": False,
                "pending_calculation": None,
                "compound_deadline": compound_deadline,
                "deadline_clarification": deadline_clarification,
                "status": "clarification_needed",
                "answer": clarification_msg,
                "confidence": 0.5,
                "steps": steps,
                "tool_calls": tool_calls,
                "citations": [],
            }

        # Bind parameters to exact immutable pending calculation ID
        calc_id = f"calc_{uuid.uuid4().hex[:8]}"
        new_pending = {
            "id": calc_id,
            "params": calc_params,
            "created_at": datetime.now(tz=IST).isoformat(),
        }

        steps.append(
            f"Created pending calculation '{calc_id}' for {calc_params['crop'].title()} "
            f"({calc_params['area']} {calc_params.get('area_unit', 'ha')}, ₹{calc_params['scale_of_finance']}/{calc_params.get('scale_of_finance_unit', 'per_ha')}). "
            f"Routing to approval gate."
        )

        return {
            "thread_id": thread_id,
            "intent": "premium_calc",
            "pending_calculation": new_pending,
            "compound_deadline": compound_deadline,
            "deadline_clarification": deadline_clarification,
            "requires_approval": True,
            "steps": steps,
            "tool_calls": tool_calls,
            "citations": [],
        }

    # Case C: Knowledge search / policy question (does NOT reuse old calculation parameters)
    steps.append("Classified query as PMFBY guideline / policy question -> Route to knowledge search")
    return {
        "thread_id": thread_id,
        "intent": "knowledge_search",
        "pending_calculation": None,  # Ensure fresh knowledge queries never inherit old calc params
        "compound_deadline": compound_deadline,
        "deadline_clarification": deadline_clarification,
        "requires_approval": False,
        "steps": steps,
        "tool_calls": tool_calls,
        "citations": [],
    }


def route_intent(state: AgentState) -> str:
    """Conditional edge router based on classified intent."""
    intent = state.get("intent")
    if intent in {"refusal", "clarification"}:
        return "terminal_response_node"
    if intent == "premium_calc":
        return "approval_gate_node"
    return "search_node"


def terminal_response_node(state: AgentState) -> Dict[str, Any]:
    """Return terminal responses (refusals, clarifications)."""
    intent = state.get("intent")
    steps = list(state.get("steps", []))

    if intent == "refusal":
        steps.append("Executed refusal: Static PMFBY records cannot check individual claim status.")
        return {
            "status": "completed",
            "requires_approval": False,
            "confidence": 0.0,
            "answer": (
                "I don't know. Static PMFBY guideline records cannot check individual "
                "farmer claim approval or policy status. Please verify directly on "
                "pmfby.gov.in (NCIP), the Crop Insurance App, or Krishi Rakshak Helpline 14447."
            ),
            "steps": steps,
        }

    return {
        "status": state.get("status", "completed"),
        "requires_approval": False,
        "answer": state.get("answer", ""),
        "confidence": state.get("confidence", 0.0),
        "steps": steps,
    }


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop approval pause for financial calculations using LangGraph interrupt()."""
    pending = state.get("pending_calculation") or {}
    params = pending.get("params") or {}
    calc_id = pending.get("id")
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    compound_deadline = state.get("compound_deadline")

    area_str = f"{params.get('area')} {params.get('area_unit', params.get('unit', 'ha'))}"
    sof_unit = "per acre" if params.get("scale_of_finance_unit") == "per_acre" else "per ha"
    sof_str = f"₹{params.get('scale_of_finance', 0):,.2f}/{sof_unit}"
    crop_str = str(params.get("crop", "crop")).title()
    season_str = str(params.get("season") or "Statutory Rate").title()

    prompt_parts = []
    if compound_deadline:
        prompt_parts.append(
            f"**Localized Calamity Intimation (72-Hour Rule):**\n"
            f"- **Statutory Window:** Must be intimated within **72 hours** of loss occurrence.\n"
            f"- **Loss Event:** {compound_deadline['loss_timestamp']}\n"
            f"- **Intimation Deadline:** **{compound_deadline['deadline_timestamp']}** ({compound_deadline['remaining_hours']}h remaining)\n"
            f"- **Reporting Channels:** {', '.join(compound_deadline['reporting_channels'])}\n"
            f"- *Governing Rule:* {compound_deadline['og_version']}\n"
        )
    elif state.get("deadline_clarification"):
        prompt_parts.append(
            f"**Localized Calamity Intimation (72-Hour Rule):**\n"
            f"{state.get('deadline_clarification')}\n"
        )

    prompt_parts.append(
        f"**Approval Required for PMFBY Calculation:**\n"
        f"- **Calculation ID:** `{calc_id}`\n"
        f"- **Crop:** {crop_str}\n"
        f"- **Season:** {season_str}\n"
        f"- **Area:** {area_str}\n"
        f"- **Scale of Finance:** {sof_str}\n\n"
        f"To proceed, approve with `approved: true`. To cancel, submit with `approved: false`."
    )
    prompt_answer = "\n".join(prompt_parts)

    interrupt_payload = {
        "calculation_id": calc_id,
        "params": params,
        "message": prompt_answer,
    }

    steps.append(f"Approval gate: Calling interrupt() for calculation ID '{calc_id}'. Pausing graph.")

    # Native LangGraph interrupt: Pauses graph until resumed with Command(resume=...)
    resume_payload = interrupt(interrupt_payload)

    # When resumed via Command(resume=...), execution continues below
    if not isinstance(resume_payload, dict):
        resume_payload = {"approved": bool(resume_payload)}

    is_approved = resume_payload.get("approved")
    resume_calc_id = resume_payload.get("calculation_id")

    # Rejection of calculation ID mismatch
    if resume_calc_id and resume_calc_id != calc_id:
        steps.append(
            f"Approval rejected: ID mismatch (expected '{calc_id}', received '{resume_calc_id}')"
        )
        return {
            "status": "rejected",
            "requires_approval": False,
            "pending_calculation": None,
            "answer": f"Approval rejected: Calculation ID mismatch. Pending calculation is '{calc_id}', but approval requested '{resume_calc_id}'.",
            "confidence": 0.0,
            "steps": steps,
            "tool_calls": tool_calls,
        }

    # User cancellation (approved=False): Must NOT execute the pending tool
    if not is_approved:
        steps.append(f"Received cancellation for calculation ID '{calc_id}'. No tools executed.")
        return {
            "status": "cancelled",
            "requires_approval": False,
            "pending_calculation": None,
            "answer": "Calculation cancelled as requested. No tools were executed and no records were submitted.",
            "confidence": 1.0,
            "steps": steps,
            "tool_calls": tool_calls,
        }

    # Approved (approved=True): Execute pmfby_premium tool using bound immutable parameters
    steps.append(f"Received user approval for calculation ID '{calc_id}'. Executing pmfby_premium.")
    try:
        calc_res = pmfby_premium(
            scale_of_finance=params.get("scale_of_finance"),
            area=params.get("area"),
            crop=params.get("crop"),
            season=params.get("season"),
            area_unit=params.get("area_unit", params.get("unit", "ha")),
            scale_of_finance_unit=params.get("scale_of_finance_unit", "per_ha"),
            actuarial_rate=params.get("actuarial_rate"),
        )
        tool_calls.append({"tool": "pmfby_premium", "input": params, "output": calc_res})
        steps.append(
            f"Tool executed: pmfby_premium -> Sum Insured: ₹{calc_res['sum_insured']:,.2f}, "
            f"Farmer Share: ₹{calc_res['farmer_premium']:,.2f}"
        )
    except Exception as err:
        return {
            "status": "error",
            "requires_approval": False,
            "pending_calculation": None,
            "answer": f"Calculation execution failed: {err}",
            "confidence": 0.0,
            "steps": steps,
            "tool_calls": tool_calls,
        }

    final_parts = []
    if compound_deadline:
        final_parts.append(
            f"**Localized Calamity Intimation (72-Hour Rule):**\n"
            f"- **Statutory Window:** Must be intimated within **72 hours** of loss occurrence.\n"
            f"- **Loss Event:** {compound_deadline['loss_timestamp']}\n"
            f"- **Intimation Deadline:** **{compound_deadline['deadline_timestamp']}** ({compound_deadline['remaining_hours']}h remaining)\n"
            f"- **Reporting Channels:** {', '.join(compound_deadline['reporting_channels'])}\n"
            f"- *Governing Rule:* {compound_deadline['og_version']}\n"
        )

    final_parts.append(
        f"**PMFBY Premium Calculation (Confirmed):**\n"
        f"- **Calculation ID:** `{calc_id}`\n"
        f"- **Sum Insured:** ₹{calc_res['sum_insured']:,.2f} "
        f"(₹{calc_res['scale_of_finance_per_ha']:,.2f}/ha × {calc_res['area_ha']:.2f} ha)\n"
        f"- **Farmer Premium Rate:** {calc_res['farmer_rate_percent']:.2f}% "
        f"({calc_res['season'].title()} {calc_res['crop'].title()})\n"
        f"- **{'Estimated Maximum ' if calc_res['is_estimated_maximum'] else ''}Farmer Premium Share:** **₹{calc_res['farmer_premium']:,.2f}**\n"
        f"- *Rate Basis:* {calc_res['rate_note']}\n"
        f"- *Governing Rule:* {calc_res['rule_reference']['rule_topic']} "
        f"({calc_res['rule_reference']['og_version']})"
    )

    return {
        "status": "completed",
        "requires_approval": False,
        "pending_calculation": None,  # Cleared after execution to prevent replay
        "answer": "\n".join(final_parts),
        "confidence": 0.95,
        "steps": steps,
        "tool_calls": tool_calls,
    }


def search_node(state: AgentState) -> Dict[str, Any]:
    """Execute pmfby_knowledge_search tool over Chroma vectorstore."""
    query = state.get("query", "")
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    citations = list(state.get("citations", []))
    compound_deadline = state.get("compound_deadline")

    try:
        search_res = pmfby_knowledge_search(query, top_k=3)
        tool_calls.append({"tool": "pmfby_knowledge_search", "input": {"query": query, "top_k": 3}, "output": search_res})
        steps.append(f"Tool executed: pmfby_knowledge_search -> Retrieved {len(search_res['hits'])} chunks")

        for hit in search_res.get("hits", []):
            citations.append(
                {
                    "source": hit.get("source"),
                    "page": hit.get("page"),
                    "title": hit.get("title"),
                    "score": hit.get("score"),
                }
            )

        answer_parts = []
        if compound_deadline:
            answer_parts.append(
                f"**Localized Calamity Intimation (72-Hour Rule):**\n"
                f"- **Statutory Window:** Must be intimated within **72 hours** of loss occurrence.\n"
                f"- **Loss Event:** {compound_deadline['loss_timestamp']}\n"
                f"- **Intimation Deadline:** **{compound_deadline['deadline_timestamp']}** ({compound_deadline['remaining_hours']}h remaining)\n"
                f"- **Reporting Channels:** {', '.join(compound_deadline['reporting_channels'])}\n"
                f"- *Governing Rule:* {compound_deadline['og_version']}"
            )
        elif state.get("deadline_clarification"):
            answer_parts.append(
                f"**Localized Calamity Intimation (72-Hour Rule):**\n"
                f"{state.get('deadline_clarification')}"
            )

        if search_res.get("hits"):
            from app.llm import generate_chat_response

            adapted_records = []
            for c in search_res.get("hits", []):
                adapted_records.append(
                    {
                        "id": c.get("id", c.get("chunk_id", 0)),
                        "rule_topic": c.get("title", "PMFBY Guideline"),
                        "rule_text": c.get("text", ""),
                        "og_version": c.get("og_version", "Revamped OG (Kharif 2020 onwards)"),
                        "applies_to": f"Page {c.get('page', 1)} of {c.get('source', '')}",
                        "deadline_or_rate": f"Page {c.get('page', 1)} of {c.get('source', '')}",
                        "source_url": c.get("source", ""),
                        "score": c.get("score", 0.0),
                    }
                )

            llm_res = generate_chat_response(
                question=query,
                prompt_version="v2",
                top_k=len(adapted_records),
                context_records=adapted_records,
            )
            answer_parts.append(llm_res.get("answer", ""))
            confidence = float(llm_res.get("confidence", 0.9))
            prov = llm_res.get("provider", "llm")
            mod = llm_res.get("model", "default")
            steps.append(f"Grounded answer synthesized using {prov} ({mod}).")
        else:
            answer_parts.append(
                "No specific matching PMFBY rule chunk found. Please consult "
                "pmfby.gov.in or call 14447 for official clarification."
            )
            confidence = 0.4

        answer = "\n\n".join(answer_parts)
    except Exception as err:
        answer = f"Knowledge base search encountered an error: {err}"
        confidence = 0.0

    return {
        "status": "completed",
        "requires_approval": False,
        "answer": answer,
        "confidence": confidence,
        "steps": steps,
        "tool_calls": tool_calls,
        "citations": citations,
    }


def build_pmfby_graph(checkpointer: Optional[Any] = None) -> Any:
    """Construct and compile the PMFBY LangGraph with memory and approval step."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("classify_node", classify_node)
    workflow.add_node("terminal_response_node", terminal_response_node)
    workflow.add_node("approval_gate_node", approval_gate_node)
    workflow.add_node("search_node", search_node)

    # Add Edges
    workflow.add_edge(START, "classify_node")

    workflow.add_conditional_edges(
        "classify_node",
        route_intent,
        {
            "terminal_response_node": "terminal_response_node",
            "approval_gate_node": "approval_gate_node",
            "search_node": "search_node",
        },
    )

    workflow.add_edge("terminal_response_node", END)
    workflow.add_edge("approval_gate_node", END)
    workflow.add_edge("search_node", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=cp)


# Shared in-memory checkpointer for active application runtime
_GLOBAL_CHECKPOINTER = MemorySaver()
pmfby_agent_graph = build_pmfby_graph(checkpointer=_GLOBAL_CHECKPOINTER)


def run_langgraph_agent(
    query: Optional[str] = None,
    thread_id: Optional[str] = None,
    approved: Optional[bool] = None,
    calculation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run or resume the LangGraph agent across conversational turns with isolated memory.

    Uses LangGraph interrupt() and Command(resume=...) to pause and resume at the approval step.
    State is persisted per thread_id in MemorySaver across turns in the process runtime.
    """
    # Enforce unique conversation ID isolation; never share a global default thread
    active_thread = thread_id.strip() if thread_id and thread_id.strip() and thread_id not in {"default", "default_thread"} else f"session_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": active_thread}}

    # Case 1: Resuming an interrupted calculation with approval (approved is True or False)
    if approved is not None:
        state_snapshot = pmfby_agent_graph.get_state(config)
        interrupt_tasks = [t for t in state_snapshot.tasks if len(t.interrupts) > 0]

        if not interrupt_tasks:
            return {
                "response_id": f"resp_{uuid.uuid4().hex[:10]}",
                "query": query or "",
                "thread_id": active_thread,
                "answer": "No pending calculation found to approve or cancel on this session. Please submit your crop, area, and scale of finance first.",
                "status": "rejected",
                "requires_approval": False,
                "intent": "approval_rejected",
                "tool_calls": [],
                "steps": ["Received approval/cancellation without an active pending calculation -> Route to rejection"],
                "citations": [],
                "confidence": 0.0,
                "disclaimer": DISCLAIMER,
            }

        # Active interrupt exists: extract bound calculation ID and immutable parameters
        active_interrupt = interrupt_tasks[0].interrupts[0]
        active_val = active_interrupt.value if hasattr(active_interrupt, "value") else {}
        expected_calc_id = active_val.get("calculation_id")
        expected_params = active_val.get("params", {})

        # Requirement 4: Require calculation_id for every approval or cancellation
        if not calculation_id or not str(calculation_id).strip():
            return {
                "response_id": f"resp_{uuid.uuid4().hex[:10]}",
                "query": query or "",
                "thread_id": active_thread,
                "answer": (
                    f"A valid 'calculation_id' is required to approve or cancel. "
                    f"The pending calculation `{expected_calc_id}` remains active."
                ),
                "status": "rejected",
                "requires_approval": True,
                "pending_calculation": {"id": expected_calc_id, "params": expected_params},
                "intent": "approval_rejected",
                "tool_calls": [],
                "steps": ["Missing calculation_id -> Preserved pending calculation and rejected approval request"],
                "citations": [],
                "confidence": 0.0,
                "disclaimer": DISCLAIMER,
            }

        # Requirement 4: Reject mismatched or stale calculation IDs WITHOUT consuming the pending interrupt
        if calculation_id.strip() != expected_calc_id:
            return {
                "response_id": f"resp_{uuid.uuid4().hex[:10]}",
                "query": query or "",
                "thread_id": active_thread,
                "answer": (
                    f"Calculation ID mismatch: received '{calculation_id}', but pending calculation is '{expected_calc_id}'. "
                    f"The pending calculation `{expected_calc_id}` remains active."
                ),
                "status": "rejected",
                "requires_approval": True,
                "pending_calculation": {"id": expected_calc_id, "params": expected_params},
                "intent": "approval_rejected",
                "tool_calls": [],
                "steps": [f"Mismatched calculation_id ('{calculation_id}' != '{expected_calc_id}') -> Preserved pending calculation and rejected"],
                "citations": [],
                "confidence": 0.0,
                "disclaimer": DISCLAIMER,
            }

        # Valid ID: Now resume LangGraph interrupt via Command(resume=...)
        resume_payload = {"approved": approved, "calculation_id": expected_calc_id}
        result = pmfby_agent_graph.invoke(Command(resume=resume_payload), config=config)
        return {
            "response_id": f"resp_{uuid.uuid4().hex[:10]}",
            "query": query or result.get("query", ""),
            "thread_id": active_thread,
            "answer": result.get("answer", ""),
            "status": result.get("status", "completed"),
            "requires_approval": result.get("requires_approval", False),
            "intent": result.get("intent", "approval_resume"),
            "tool_calls": result.get("tool_calls", []),
            "steps": result.get("steps", []),
            "citations": result.get("citations", []),
            "confidence": result.get("confidence", 0.0),
            "disclaimer": DISCLAIMER,
        }

    # Case 2: New user query turn
    input_payload: Dict[str, Any] = {"thread_id": active_thread, "query": query or ""}
    result = pmfby_agent_graph.invoke(input_payload, config=config)

    # Check if the graph paused at an interrupt()
    if "__interrupt__" in result and result["__interrupt__"]:
        interrupt_val = result["__interrupt__"][0].value
        return {
            "response_id": f"resp_{uuid.uuid4().hex[:10]}",
            "query": query or "",
            "thread_id": active_thread,
            "answer": interrupt_val.get("message", "Approval required for calculation."),
            "status": "approval_required",
            "requires_approval": True,
            "intent": "premium_calc",
            "pending_calculation": {"id": interrupt_val.get("calculation_id"), "params": interrupt_val.get("params")},
            "tool_calls": [],
            "steps": ["Approval gate: Pausing for user confirmation via LangGraph interrupt()."],
            "citations": [],
            "confidence": 0.8,
            "disclaimer": DISCLAIMER,
        }

    return {
        "response_id": f"resp_{uuid.uuid4().hex[:10]}",
        "query": query or result.get("query", ""),
        "thread_id": active_thread,
        "answer": result.get("answer", ""),
        "status": result.get("status", "completed"),
        "requires_approval": result.get("requires_approval", False),
        "intent": result.get("intent", ""),
        "tool_calls": result.get("tool_calls", []),
        "steps": result.get("steps", []),
        "citations": result.get("citations", []),
        "confidence": result.get("confidence", 0.0),
        "disclaimer": DISCLAIMER,
    }
