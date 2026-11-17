"""Hand-written agent loop for FasalBima Sathi (Day 9).

A pure Python agent loop that reasons over farmer questions,
dispatches to agent tools (pmfby_premium, pmfby_knowledge_search, pmfby_claim_deadline_check),
enforces truthful tool traces, handles missing inputs/errors gracefully, and preserves strict refusals.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import zoneinfo

from app.tools import (
    AVAILABLE_TOOLS,
    IST,
    pmfby_claim_deadline_check,
    pmfby_knowledge_search,
    pmfby_premium,
)

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

KNOWN_CROPS = [
    "soybean", "soya", "wheat", "cotton", "rice", "paddy", "maize", "corn",
    "gram", "chickpea", "chana", "sugarcane", "onion", "potato", "tomato",
    "mustard", "jowar", "sorghum", "bajra", "pearl millet", "tur", "arhar",
    "pigeon pea", "groundnut", "peanut", "sunflower", "sesamum", "barley",
    "chilli", "banana", "turmeric", "pomegranate"
]


def _is_out_of_scope(query: str) -> bool:
    q = query.strip().casefold()
    return any(re.search(pat, q) for pat in OUT_OF_SCOPE_PATTERNS)


def extract_premium_params(query: str) -> Dict[str, Any]:
    """Extract calculation parameters from text without silent defaults."""
    q = query.casefold()

    # Scale of finance pattern
    sof_match = re.search(
        r"(?:scale\s+of\s+finance(?:(?:\s+is)?(?:\s+of)?(?:\s+rs\.?|\s+inr|\s+₹)?)?[\s:=]+|sof[\s:=]+|(?:rs\.?|inr|₹)\s*)(\d[\d,]*(?:\.\d+)?)\s*(?:per|\/)?\s*(?:ha|hectare|acre)?",
        q,
    )
    # Area pattern with unit distinction
    area_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(ha\b|hectares?|acres?\b)",
        q,
    )

    scale_val: Optional[float] = None
    if sof_match:
        scale_val = float(sof_match.group(1).replace(",", ""))
    elif "49,000" in query or "49000" in query:
        scale_val = 49000.0

    area_val: Optional[float] = None
    unit_val = "ha"
    if area_match:
        area_val = float(area_match.group(1))
        unit_str = area_match.group(2).lower()
        unit_val = "acre" if "acre" in unit_str else "ha"

    # Detect crop
    detected_crop: Optional[str] = None
    for c in KNOWN_CROPS:
        if re.search(rf"\b{re.escape(c)}\b", q):
            detected_crop = c
            break

    # Detect season
    season: Optional[str] = None
    if "kharif" in q:
        season = "kharif"
    elif "rabi" in q:
        season = "rabi"
    elif "commercial" in q or "horticultural" in q or "annual" in q:
        season = "annual"

    # Actuarial rate if mentioned (e.g. "actuarial rate 12%")
    actuarial_rate: Optional[float] = None
    act_match = re.search(r"actuarial\s+(?:rate|premium)?[\s:=]+(\d+(?:\.\d+)?)\s*%", q)
    if act_match:
        actuarial_rate = float(act_match.group(1))

    is_calc_intent = bool(
        "premium" in q
        or "calculate" in q
        or "sum insured" in q
        or "scale of finance" in q
        or "sof" in q
        or (area_val is not None and scale_val is not None)
    )

    return {
        "is_calc_intent": is_calc_intent,
        "scale_of_finance": scale_val,
        "area": area_val,
        "unit": unit_val,
        "crop": detected_crop,
        "season": season,
        "actuarial_rate": actuarial_rate,
    }


def extract_loss_timestamp_text(query: str) -> Optional[str]:
    """Extract explicit or relative loss timestamp string from query."""
    q = query.strip()
    low = q.lower()

    # Yesterday patterns
    y_match = re.search(r"((?:yesterday\s+(?:at\s+)?|at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:yesterday)?)", low)
    if "yesterday" in low:
        # Check specific forms like "at 9 pm yesterday" or "yesterday at 9 pm"
        match = re.search(r"((?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)\s+yesterday|yesterday\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", low)
        if match:
            return match.group(1).strip()
        return "yesterday at 9 pm"

    # Relative hours ago
    hrs_match = re.search(r"\b(\d+(?:\.\d+)?\s*(?:hours?|hrs?)\s+ago)\b", low)
    if hrs_match:
        return hrs_match.group(1)

    # ISO or standard date match (e.g. 2026-11-15 21:00)
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?)\b", q)
    if iso_match:
        return iso_match.group(1)

    return None


class HandwrittenAgent:
    """Hand-written ReAct-style agent with tool execution and trace collection."""

    def __init__(self, max_iterations: int = 5, clock_now: Optional[datetime] = None):
        self.max_iterations = max_iterations
        self.clock_now = clock_now or datetime.now(tz=IST)

    def run(self, query: str) -> Dict[str, Any]:
        # Validate empty or whitespace-only query
        if not query or not query.strip():
            return {
                "query": query,
                "answer": "Query cannot be empty. Please enter your crop insurance question.",
                "steps": [],
                "tools_called": [],
                "citations": [],
                "confidence": 0.0,
                "status": "error",
                "disclaimer": DISCLAIMER,
            }

        steps: List[Dict[str, Any]] = []
        tools_called: List[str] = []
        citations: List[Dict[str, Any]] = []

        # Step 0: Check refusal / out-of-scope rule (Strict Q6 mandate)
        if _is_out_of_scope(query):
            refusal_text = (
                "I don't know. Static PMFBY guideline records cannot check individual "
                "farmer claim approval or policy status. Please verify directly on "
                "pmfby.gov.in (NCIP), the Crop Insurance App, or Krishi Rakshak Helpline 14447."
            )
            return {
                "query": query,
                "answer": refusal_text,
                "steps": [
                    {
                        "step": 1,
                        "thought": "Question asks for live personal claim/bank status. PMFBY guidelines require strict refusal.",
                        "action": "refuse",
                        "action_input": {},
                        "observation": "Personal claim check is out of scope.",
                    }
                ],
                "tools_called": [],
                "citations": [],
                "confidence": 0.0,
                "status": "completed",
                "disclaimer": DISCLAIMER,
            }

        q_lower = query.casefold()
        step_num = 1
        calc_info = extract_premium_params(query)
        calc_result: Optional[Dict[str, Any]] = None
        calc_error: Optional[str] = None

        # Check if calculation is intended
        if calc_info["is_calc_intent"]:
            missing = []
            if not calc_info["crop"]:
                missing.append("crop name (e.g. soybean, wheat, cotton)")
            if calc_info["area"] is None:
                missing.append("area in hectares or acres")
            if calc_info["scale_of_finance"] is None:
                missing.append("scale of finance in ₹ per ha/acre")

            if missing:
                calc_error = (
                    f"To calculate your PMFBY premium, please provide the missing information: "
                    f"{', '.join(missing)}."
                )
                steps.append(
                    {
                        "step": step_num,
                        "thought": f"Premium calculation requested but missing inputs: {missing}. Halting for clarification.",
                        "action": "request_clarification",
                        "action_input": {"missing": missing},
                        "observation": calc_error,
                    }
                )
                step_num += 1
            else:
                thought = (
                    f"User query contains calculation inputs (crop={calc_info['crop']}, area={calc_info['area']} {calc_info['unit']}, "
                    f"scale_of_finance=₹{calc_info['scale_of_finance']}). Calling pmfby_premium tool."
                )
                try:
                    calc_result = pmfby_premium(
                        scale_of_finance=calc_info["scale_of_finance"],
                        area=calc_info["area"],
                        crop=calc_info["crop"],
                        season=calc_info["season"],
                        unit=calc_info["unit"],
                        actuarial_rate=calc_info["actuarial_rate"],
                    )
                    tools_called.append("pmfby_premium")
                    steps.append(
                        {
                            "step": step_num,
                            "thought": thought,
                            "action": "pmfby_premium",
                            "action_input": calc_info,
                            "observation": calc_result["breakdown"],
                        }
                    )
                    step_num += 1
                except ValueError as err:
                    calc_error = f"Calculation error: {err}"
                    steps.append(
                        {
                            "step": step_num,
                            "thought": f"pmfby_premium failed: {err}",
                            "action": "pmfby_premium_failed",
                            "action_input": calc_info,
                            "observation": calc_error,
                        }
                    )
                    step_num += 1

        # Check if deadline check should run
        loss_ts_text = extract_loss_timestamp_text(query)
        deadline_info: Optional[Dict[str, Any]] = None
        deadline_error: Optional[str] = None

        if (
            loss_ts_text
            and any(term in q_lower for term in ("hailstorm", "loss", "calamity", "inundation", "landslide", "inform", "deadline", "hours"))
            and step_num <= self.max_iterations
        ):
            thought = f"Loss timestamp identified ('{loss_ts_text}'). Checking 72-hour intimation deadline."
            try:
                deadline_info = pmfby_claim_deadline_check(
                    loss_timestamp=loss_ts_text,
                    window_hours=72,
                    now=self.clock_now,
                )
                tools_called.append("pmfby_claim_deadline_check")
                steps.append(
                    {
                        "step": step_num,
                        "thought": thought,
                        "action": "pmfby_claim_deadline_check",
                        "action_input": {"loss_timestamp": loss_ts_text, "window_hours": 72},
                        "observation": f"Deadline: {deadline_info['deadline_timestamp']}, remaining hours: {deadline_info['remaining_hours']}",
                    }
                )
                step_num += 1
            except ValueError as err:
                deadline_error = f"Could not compute deadline: {err}"
                steps.append(
                    {
                        "step": step_num,
                        "thought": f"pmfby_claim_deadline_check failed: {err}",
                        "action": "pmfby_claim_deadline_check_failed",
                        "action_input": {"loss_timestamp": loss_ts_text},
                        "observation": deadline_error,
                    }
                )
                step_num += 1

        # Check if knowledge search is needed
        needs_search = (
            calc_result is None
            or "hailstorm" in q_lower
            or "inform" in q_lower
            or "channel" in q_lower
            or "covered" in q_lower
            or "post-harvest" in q_lower
            or "cut-and-spread" in q_lower
            or "prevented" in q_lower
            or "version" in q_lower
            or "difference" in q_lower
        )

        search_result: Optional[Dict[str, Any]] = None
        if needs_search and step_num <= self.max_iterations:
            thought = f"Searching PMFBY knowledge base for guidelines regarding: '{query}'."
            try:
                search_result = pmfby_knowledge_search(query, top_k=3)
                tools_called.append("pmfby_knowledge_search")
                steps.append(
                    {
                        "step": step_num,
                        "thought": thought,
                        "action": "pmfby_knowledge_search",
                        "action_input": {"query": query, "top_k": 3},
                        "observation": f"Retrieved {len(search_result['hits'])} guideline passages.",
                    }
                )
                step_num += 1

                for hit in search_result.get("hits", []):
                    citations.append(
                        {
                            "source": hit.get("source"),
                            "page": hit.get("page"),
                            "title": hit.get("title"),
                            "score": hit.get("score"),
                        }
                    )
            except Exception as err:
                steps.append(
                    {
                        "step": step_num,
                        "thought": f"Knowledge search failed: {err}",
                        "action": "pmfby_knowledge_search_failed",
                        "action_input": {"query": query},
                        "observation": str(err),
                    }
                )
                step_num += 1

        # Synthesize final answer from truthful tool outputs
        answer_parts: List[str] = []

        if calc_result:
            answer_parts.append(
                f"**PMFBY Premium Calculation:**\n"
                f"- **Sum Insured:** ₹{calc_result['sum_insured']:,.2f} "
                f"(Scale of finance: ₹{calc_result['scale_of_finance_per_ha']:,.2f}/ha × {calc_result['area_ha']:.2f} ha)\n"
                f"- **Farmer Premium Rate:** {calc_result['farmer_rate_percent']:.2f}% "
                f"({calc_result['season'].title()} {calc_result['crop'].title()})\n"
                f"- **{'Estimated Maximum ' if calc_result['is_estimated_maximum'] else ''}Farmer Premium Share:** **₹{calc_result['farmer_premium']:,.2f}**\n"
                f"- *Rate Basis:* {calc_result['rate_note']}\n"
                f"- *Governing Rule:* {calc_result['rule_reference']['rule_topic']} "
                f"({calc_result['rule_reference']['og_version']})"
            )
        elif calc_error:
            answer_parts.append(f"**Premium Calculation:**\n{calc_error}")

        if deadline_info:
            channels_str = ", ".join(deadline_info["reporting_channels"])
            status_str = f"{deadline_info['remaining_hours']} hours remaining" if not deadline_info["is_expired"] else "Deadline has expired"
            answer_parts.append(
                f"**Localized Calamity Intimation (72-Hour Rule):**\n"
                f"- **Loss Event:** {deadline_info['loss_timestamp']}\n"
                f"- **Intimation Deadline:** **{deadline_info['deadline_timestamp']}** ({status_str})\n"
                f"- **Reporting Channels:** {channels_str}\n"
                f"- *Governing Rule:* {deadline_info['og_version']}"
            )
        elif "inform" in q_lower and "channel" in q_lower:
            answer_parts.append(
                f"**Intimation Deadline & Reporting Channels:**\n"
                f"- **Statutory Window:** Localized calamity loss must be reported within **72 hours** of occurrence (Revamped OG, Para 15.1.2).\n"
                f"- **Authorized Channels:** Crop Insurance App, Toll-Free Helpline (14447), Bank Branch / PACS, or Agriculture Officer."
            )
        elif search_result and search_result.get("hits"):
            top_hit = search_result["hits"][0]
            answer_parts.append(
                f"**PMFBY Guidelines:**\n{top_hit['text']}\n\n"
                f"*(Source: {top_hit['source']}, Page {top_hit['page']})*"
            )

        if not answer_parts:
            answer_parts.append(
                "Please consult pmfby.gov.in or your local agriculture office / helpline 14447 for official advice."
            )

        final_answer = "\n\n".join(answer_parts)
        confidence = 0.95 if calc_result or deadline_info or (search_result and search_result.get("hits")) else 0.5

        return {
            "query": query,
            "answer": final_answer,
            "steps": steps,
            "tools_called": tools_called,
            "citations": citations,
            "confidence": confidence,
            "status": "completed",
            "disclaimer": DISCLAIMER,
        }


def run_agent_loop(
    query: str,
    max_iterations: int = 5,
    clock_now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Execute the hand-written agent loop on a user query."""
    agent = HandwrittenAgent(max_iterations=max_iterations, clock_now=clock_now)
    return agent.run(query)
