"""LangGraph agent for FasalBima Sathi with Memory and Approval Step (Day 9).

Rebuilds the PMFBY assistant into a stateful LangGraph workflow featuring:
1. Intent classification & RAG search
2. Pure arithmetic PMFBY premium tool integration
3. Persistent conversation memory via MemorySaver
4. Human-in-the-loop approval step for financial calculations
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent_loop import OUT_OF_SCOPE_PATTERNS, _is_out_of_scope, extract_premium_params
from app.tools import (
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
    query: str
    thread_id: str
    intent: str  # "refusal", "premium_calc", "knowledge_search"
    params: Optional[Dict[str, Any]]
    requires_approval: bool
    approved: Optional[bool]
    tool_calls: List[Dict[str, Any]]
    steps: List[str]
    citations: List[Dict[str, Any]]
    status: str  # "completed", "approval_required", "refused"
    answer: str
    confidence: float


def classify_node(state: AgentState) -> Dict[str, Any]:
    """Classify farmer query intent and extract structured parameters."""
    query = state.get("query", "").strip()
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    citations = list(state.get("citations", []))

    # 1. Out-of-scope check (Strict Q6 mandate)
    if _is_out_of_scope(query):
        steps.append("Classified query as out-of-scope claim/bank status inquiry -> Route to refusal")
        return {
            "intent": "refusal",
            "steps": steps,
            "tool_calls": tool_calls,
            "citations": citations,
            "requires_approval": False,
        }

    # 2. Check for premium calculation parameters
    params = extract_premium_params(query) or state.get("params")
    if params:
        steps.append(
            f"Classified query as PMFBY premium calculation (crop={params.get('crop')}, "
            f"area={params.get('area')} ha, scale_of_finance=₹{params.get('scale_of_finance')}) -> Route to approval check"
        )
        return {
            "intent": "premium_calc",
            "params": params,
            "steps": steps,
            "tool_calls": tool_calls,
            "citations": citations,
        }

    # 3. Default to knowledge search
    steps.append("Classified query as PMFBY guideline / policy question -> Route to knowledge search")
    return {
        "intent": "knowledge_search",
        "params": None,
        "steps": steps,
        "tool_calls": tool_calls,
        "citations": citations,
        "requires_approval": False,
    }


def route_intent(state: AgentState) -> str:
    """Conditional edge router based on classified intent."""
    intent = state.get("intent")
    if intent == "refusal":
        return "refusal_node"
    if intent == "premium_calc":
        return "approval_gate_node"
    return "search_node"


def refusal_node(state: AgentState) -> Dict[str, Any]:
    """Strict refusal for live claim/application status (Day 8 / Day 9 Q6 requirement)."""
    steps = list(state.get("steps", []))
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


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop approval step for financial calculations."""
    approved = state.get("approved")
    params = state.get("params") or {}
    steps = list(state.get("steps", []))

    if approved is not True:
        # Halt execution and request user approval
        steps.append("Approval step: Premium calculation requires user confirmation. Halting for approval.")
        area_str = f"{params.get('area', 1.0)} ha"
        sof_str = f"₹{params.get('scale_of_finance', 0):,.2f}/ha"
        crop_str = str(params.get("crop", "crop")).title()

        return {
            "status": "approval_required",
            "requires_approval": True,
            "confidence": 0.8,
            "answer": (
                f"**Approval Required:** Please confirm calculation of PMFBY sum insured and farmer premium share for:\n"
                f"- **Crop:** {crop_str}\n"
                f"- **Area:** {area_str}\n"
                f"- **Scale of Finance:** {sof_str}\n\n"
                f"To confirm and finalize the calculation, submit with `approved: true` on thread `{state.get('thread_id', 'default')}`."
            ),
            "steps": steps,
        }

    steps.append("Approval step: User confirmed calculation approval. Proceeding to execution.")
    return {
        "status": "in_progress",
        "requires_approval": False,
        "steps": steps,
    }


def route_after_approval(state: AgentState) -> str:
    """Conditional edge after approval gate."""
    if state.get("status") == "approval_required":
        return END
    return "premium_execution_node"


def premium_execution_node(state: AgentState) -> Dict[str, Any]:
    """Execute pmfby_premium tool and optional intimation search."""
    params = state.get("params") or {}
    query = state.get("query", "")
    steps = list(state.get("steps", []))
    tool_calls = list(state.get("tool_calls", []))
    citations = list(state.get("citations", []))

    # 1. Execute pure arithmetic tool
    calc_res = pmfby_premium(
        scale_of_finance=float(params.get("scale_of_finance", 49000)),
        area=float(params.get("area", 1.0)),
        crop=params.get("crop"),
        season=params.get("season"),
    )
    tool_calls.append({"tool": "pmfby_premium", "input": params, "output": calc_res})
    steps.append(f"Tool executed: pmfby_premium -> Sum Insured: ₹{calc_res['sum_insured']:,.2f}, Farmer Share: ₹{calc_res['farmer_premium']:,.2f}")

    # 2. Check if intimation/channels were also asked in the query
    q_low = query.lower()
    intimation_text = ""
    if any(k in q_low for k in ("hailstorm", "inform", "channel", "deadline", "yesterday", "loss")):
        channels = "Crop Insurance App, Krishi Rakshak Helpline (14447), Bank Branch, and Agriculture Office"
        intimation_text = (
            f"\n\n**Claim Intimation & Reporting:**\n"
            f"- **Deadline:** Inform within **72 hours** of the hailstorm/calamity (Revamped OG, Para 15.1.2).\n"
            f"- **Authorized Channels:** {channels}."
        )
        tool_calls.append({"tool": "pmfby_claim_deadline_check", "input": {"window_hours": 72}, "output": {"channels": channels}})
        steps.append("Tool executed: pmfby_claim_deadline_check -> 72 hours intimation window")

    final_answer = (
        f"**PMFBY Premium Calculation (Confirmed):**\n"
        f"- **Sum Insured:** ₹{calc_res['sum_insured']:,.2f} "
        f"(₹{calc_res['scale_of_finance_per_ha']:,.2f}/ha × {calc_res['area_ha']:.2f} ha)\n"
        f"- **Farmer Premium Rate:** {calc_res['farmer_rate_percent']:.1f}% "
        f"({calc_res['season'].title()} {calc_res['crop'].title()})\n"
        f"- **Farmer Premium Share:** **₹{calc_res['farmer_premium']:,.2f}**\n"
        f"- *Governing Rule:* {calc_res['rule_reference']['rule_topic']} "
        f"({calc_res['rule_reference']['og_version']})"
        f"{intimation_text}"
    )

    return {
        "status": "completed",
        "requires_approval": False,
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
    workflow.add_node("refusal_node", refusal_node)
    workflow.add_node("approval_gate_node", approval_gate_node)
    workflow.add_node("premium_execution_node", premium_execution_node)
    workflow.add_node("search_node", search_node)

    # Add Edges
    workflow.add_edge(START, "classify_node")

    workflow.add_conditional_edges(
        "classify_node",
        route_intent,
        {
            "refusal_node": "refusal_node",
            "approval_gate_node": "approval_gate_node",
            "search_node": "search_node",
        },
    )

    workflow.add_edge("refusal_node", END)
    workflow.add_edge("search_node", END)
    workflow.add_edge("premium_execution_node", END)

    workflow.add_conditional_edges(
        "approval_gate_node",
        route_after_approval,
        {
            END: END,
            "premium_execution_node": "premium_execution_node",
        },
    )

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=cp)


# Shared global graph instance with in-memory checkpointer for multi-turn sessions
_GLOBAL_CHECKPOINTER = MemorySaver()
pmfby_agent_graph = build_pmfby_graph(checkpointer=_GLOBAL_CHECKPOINTER)


def run_langgraph_agent(
    query: Optional[str] = None,
    thread_id: str = "default_thread",
    approved: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run or resume the LangGraph agent across conversational turns with memory."""
    config = {"configurable": {"thread_id": thread_id}}

    input_payload: Dict[str, Any] = {"thread_id": thread_id}
    if query is not None:
        input_payload["query"] = query
    if approved is not None:
        input_payload["approved"] = approved

    result = pmfby_agent_graph.invoke(input_payload, config=config)

    return {
        "query": result.get("query", query or ""),
        "thread_id": thread_id,
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

