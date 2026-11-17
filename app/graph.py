"""LangGraph agent for FasalBima Sathi with Memory and Approval Step (Day 9).

Rebuilds the PMFBY assistant into a stateful LangGraph workflow featuring:
1. Intent classification & RAG search
2. Pure arithmetic PMFBY premium tool integration with Decimal precision
3. Stateful conversation memory via LangGraph MemorySaver
4. Strict human-in-the-loop approval step with parameter binding, cancellation, and replay protection

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

from app.agent_loop import OUT_OF_SCOPE_PATTERNS, _is_out_of_scope, extract_premium_params
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
    intent: str  # "refusal", "premium_calc", "knowledge_search", "approval_resume", "approval_cancel"
    pending_calculation: Optional[Dict[str, Any]]
    requires_approval: bool
    approved: Optional[bool]
    tool_calls: List[Dict[str, Any]]
    steps: List[str]
    citations: List[Dict[str, Any]]
    status: str  # "completed", "approval_required", "cancelled", "rejected", "clarification_needed"
    answer: str
    confidence: float


def classify_node(state: AgentState) -> Dict[str, Any]:
    """Classify farmer query intent and manage approval lifecycle."""
    query = (state.get("query") or "").strip()
    thread_id = state.get("thread_id") or f"session_{uuid.uuid4().hex[:12]}"
    approved_flag = state.get("approved")
    pending_calc = state.get("pending_calculation")

    # Start fresh request-level traces
    steps: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    # Case A: User is submitting an approval confirmation (approved=True) or cancellation (approved=False)
    if approved_flag is False:
        steps.append("Received approval cancellation (approved=False) -> Route to cancel")
        return {
            "thread_id": thread_id,
            "intent": "approval_cancel",
            "requires_approval": False,
            "pending_calculation": None,
            "approved": None,
            "status": "cancelled",
            "answer": "Calculation cancelled as requested. No tools were executed and no records were submitted.",
            "confidence": 1.0,
            "steps": steps,
            "tool_calls": [],
            "citations": [],
        }

    if approved_flag is True:
        if pending_calc is None:
            steps.append("Received approval without an active pending calculation -> Route to rejection")
            return {
                "thread_id": thread_id,
                "intent": "approval_rejected",
                "requires_approval": False,
                "approved": None,
                "status": "rejected",
                "answer": "No pending calculation found to approve on this session. Please submit your crop, area, and scale of finance first.",
                "confidence": 0.0,
                "steps": steps,
                "tool_calls": [],
                "citations": [],
            }

        steps.append(f"Received user approval for calculation ID '{pending_calc.get('id')}'. Proceeding to execution.")
        return {
            "thread_id": thread_id,
            "intent": "approval_resume",
            "requires_approval": False,
            "approved": None,
            "steps": steps,
            "tool_calls": [],
            "citations": [],
        }

    # Case B: Out-of-scope check (Strict Q6 mandate)
    if _is_out_of_scope(query):
        steps.append("Classified query as out-of-scope personal claim/bank status -> Route to refusal")
        return {
            "thread_id": thread_id,
            "intent": "refusal",
            "requires_approval": False,
            "steps": steps,
            "tool_calls": [],
            "citations": [],
        }

    # Case C: Check if a NEW calculation is requested
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
            clarification_msg = (
                f"To calculate your PMFBY premium, please specify: {', '.join(missing)}."
            )
            return {
                "thread_id": thread_id,
                "intent": "clarification",
                "requires_approval": False,
                "pending_calculation": None,
                "status": "clarification_needed",
                "answer": clarification_msg,
                "confidence": 0.5,
                "steps": steps,
                "tool_calls": [],
                "citations": [],
            }

        # Bind parameters to exact pending calculation ID
        calc_id = f"calc_{uuid.uuid4().hex[:8]}"
        new_pending = {
            "id": calc_id,
            "params": calc_params,
            "created_at": datetime.now(tz=IST).isoformat(),
        }

        steps.append(
            f"Created pending calculation '{calc_id}' for {calc_params['crop'].title()} "
            f"({calc_params['area']} {calc_params['unit']}, ₹{calc_params['scale_of_finance']}/ha). "
            f"Resetting approval -> Route to approval gate."
        )

        return {
            "thread_id": thread_id,
            "intent": "premium_calc",
            "pending_calculation": new_pending,
            "approved": None,  # Always reset approval for every NEW calculation
            "requires_approval": True,
            "steps": steps,
            "tool_calls": [],
            "citations": [],
        }

    # Case D: New Knowledge search question (does NOT reuse old calculation parameters)
    steps.append("Classified query as PMFBY guideline / policy question -> Route to knowledge search")
    return {
        "thread_id": thread_id,
        "intent": "knowledge_search",
        "requires_approval": False,
        "steps": steps,
        "tool_calls": [],
        "citations": [],
    }


def route_intent(state: AgentState) -> str:
    """Conditional edge router based on classified intent."""
    intent = state.get("intent")
    if intent in {"refusal", "approval_rejected", "approval_cancel", "clarification"}:
        return "terminal_response_node"
    if intent == "premium_calc":
        return "approval_gate_node"
    if intent == "approval_resume":
        return "premium_execution_node"
    return "search_node"


def terminal_response_node(state: AgentState) -> Dict[str, Any]:
    """Return terminal responses (refusals, cancellations, clarifications)."""
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

    # For other terminal states (cancelled, rejected, clarification), state answer is already set
    return {
        "status": state.get("status", "completed"),
        "requires_approval": False,
        "answer": state.get("answer", ""),
        "confidence": state.get("confidence", 0.0),
        "steps": steps,
    }


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop approval pause for financial calculations."""
    pending = state.get("pending_calculation") or {}
    params = pending.get("params") or {}
    steps = list(state.get("steps", []))

    steps.append(f"Approval gate: Pausing for user confirmation on calculation ID '{pending.get('id')}'.")
    area_str = f"{params.get('area')} {params.get('unit', 'ha')}"
    sof_str = f"₹{params.get('scale_of_finance', 0):,.2f}/ha"
    crop_str = str(params.get("crop", "crop")).title()
    season_str = str(params.get("season", "Not specified")).title()

    answer = (
        f"**Approval Required for PMFBY Calculation:**\n"
        f"- **Calculation ID:** `{pending.get('id')}`\n"
        f"- **Crop:** {crop_str}\n"
        f"- **Season:** {season_str}\n"
        f"- **Area:** {area_str}\n"
        f"- **Scale of Finance:** {sof_str}\n\n"
        f"To proceed, submit with `approved: true` on session `{state.get('thread_id')}`. "
        f"To cancel, submit with `approved: false`."
    )

    return {
        "status": "approval_required",
        "requires_approval": True,
        "confidence": 0.8,
        "answer": answer,
        "steps": steps,
    }


def premium_execution_node(state: AgentState) -> Dict[str, Any]:
    """Execute pmfby_premium tool using the exact parameters bound to pending calculation."""
    pending = state.get("pending_calculation") or {}
    params = pending.get("params") or {}
    query = state.get("query", "")
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    citations = list(state.get("citations", []))

    try:
        calc_res = pmfby_premium(
            scale_of_finance=params.get("scale_of_finance"),
            area=params.get("area"),
            crop=params.get("crop"),
            season=params.get("season"),
            unit=params.get("unit", "ha"),
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

    # Final answer formatting
    final_answer = (
        f"**PMFBY Premium Calculation (Confirmed):**\n"
        f"- **Calculation ID:** `{pending.get('id')}`\n"
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
        "approved": None,  # Reset approved so subsequent requests start clean
        "pending_calculation": None,  # Cleared after execution to prevent replay
        "answer": final_answer,
        "confidence": 0.95,
        "steps": steps,
        "tool_calls": tool_calls,
        "citations": citations,
    }


def search_node(state: AgentState) -> Dict[str, Any]:
    """Execute pmfby_knowledge_search tool over Chroma vectorstore."""
    query = state.get("query", "")
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    citations = list(state.get("citations", []))

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

        if search_res.get("hits"):
            top_hit = search_res["hits"][0]
            answer = f"**PMFBY Guidelines:**\n{top_hit['text']}\n\n*(Source: {top_hit['source']}, Page {top_hit['page']})*"
            confidence = 0.9
        else:
            answer = (
                "No specific matching PMFBY rule chunk found. Please consult "
                "pmfby.gov.in or call 14447 for official clarification."
            )
            confidence = 0.4
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
    workflow.add_node("premium_execution_node", premium_execution_node)
    workflow.add_node("search_node", search_node)

    # Add Edges
    workflow.add_edge(START, "classify_node")

    workflow.add_conditional_edges(
        "classify_node",
        route_intent,
        {
            "terminal_response_node": "terminal_response_node",
            "approval_gate_node": "approval_gate_node",
            "premium_execution_node": "premium_execution_node",
            "search_node": "search_node",
        },
    )

    workflow.add_edge("terminal_response_node", END)
    workflow.add_edge("approval_gate_node", END)
    workflow.add_edge("premium_execution_node", END)
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
) -> Dict[str, Any]:
    """Run or resume the LangGraph agent across conversational turns with isolated memory."""
    # Enforce unique conversation ID isolation; never share a global default thread
    active_thread = thread_id.strip() if thread_id and thread_id.strip() and thread_id not in {"default", "default_thread"} else f"session_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": active_thread}}

    input_payload: Dict[str, Any] = {"thread_id": active_thread}
    if query is not None:
        input_payload["query"] = query
        input_payload["approved"] = approved  # explicitly override previous turn's approved state
    elif approved is not None:
        input_payload["approved"] = approved

    result = pmfby_agent_graph.invoke(input_payload, config=config)

    return {
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
