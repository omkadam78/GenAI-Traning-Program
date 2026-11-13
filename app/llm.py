"""LLM provider wrapper for Groq and Gemini with FasalBima Sathi prompts."""
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv
import requests

from app.records import load_records
from app.smart_search import smart_search

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PROMPTS_DIR = ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"
PROMPT_V1_PATH = PROMPTS_DIR / "task_v1_concise.txt"
PROMPT_V2_PATH = PROMPTS_DIR / "task_v2_detailed.txt"

GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GEMINI_DEFAULT_MODEL = "gemini-1.5-flash"

OUT_OF_SCOPE_PATTERNS = (
    r"\bmy\s+(?:pmfby\s+)?claim\b.*\bapproved\b",
    r"\bclaim\s+status\b",
    r"\bapplication\s+(?:status|number)\b",
    r"\bhas\s+my\b.*\bapproved\b",
    r"\bpolicy\s+status\b",
    r"\bcredit(?:ed)?\s+to\s+my\s+bank\b",
)


def load_prompt_file(path: Path) -> str:
    """Load text prompt from file with UTF-8 encoding."""
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def is_personal_claim_query(question: str) -> bool:
    """Detect private individual claim or policy status queries."""
    q = (question or "").strip().casefold()
    return any(re.search(pat, q) for pat in OUT_OF_SCOPE_PATTERNS)


def get_configured_provider() -> tuple[str, str, str]:
    """Return (provider_name, api_key, model_name)."""
    pref = os.environ.get("LLM_PROVIDER", "").strip().lower()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if pref == "groq" and groq_key:
        return "groq", groq_key, os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)
    if pref == "gemini" and gemini_key:
        return "gemini", gemini_key, os.environ.get("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)

    if groq_key:
        return "groq", groq_key, os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)
    if gemini_key:
        return "gemini", gemini_key, os.environ.get("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)

    return "offline", "", "rule-engine-fallback"


def _call_groq(
    api_key: str, model: str, system_prompt: str, user_prompt: str, timeout: int = 30
) -> dict:
    """Call Groq OpenAI-compatible Chat Completions API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    return json.loads(raw)


def _call_gemini(
    api_key: str, model: str, system_prompt: str, user_prompt: str, timeout: int = 30
) -> dict:
    """Call Google Gemini generateContent REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    if not candidates:
        raise ValueError("No candidates returned by Gemini API")
    text = candidates[0]["content"]["parts"][0]["text"]
    return json.loads(text)


def _offline_fallback(question: str, matches: list[dict], prompt_version: str) -> dict:
    """High-fidelity local fallback grounded in loaded PMFBY records."""
    if not matches:
        return {
            "answer": "I don't know. No matching PMFBY rule record was found in the dataset.",
            "confidence": 0.2,
            "follow_up": "Would you like to search by a different crop, state, or loss peril?",
        }

    top = matches[0]
    topic = top.get("rule_topic", "")
    rule_text = top.get("rule_text", "")
    rate = top.get("deadline_or_rate", "")
    ver = top.get("og_version", "")

    if prompt_version == "v1":
        # Concise version
        answer = f"Under {ver}, {topic} specifies that {rule_text} [Key rate/deadline: {rate}]."
        follow_up = "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
        confidence = 0.95
    else:
        # Detailed structured version
        answer = (
            f"According to {ver}:\n\n"
            f"1. **Policy Provision**: {topic} — {rule_text}\n"
            f"2. **Applicable Rate / Timeline**: {rate}\n"
            f"3. **Scope & Application**: Applicable to {top.get('applies_to', 'Notified crops/areas')}.\n\n"
            f"For localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department."
        )
        follow_up = "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
        confidence = 0.98

    return {
        "answer": answer,
        "confidence": confidence,
        "follow_up": follow_up,
    }


def generate_chat_response(
    question: str,
    prompt_version: str = "v2",
    top_k: int = 3,
    context_records: list[dict] | None = None,
) -> dict[str, Any]:
    """Generate a structured PMFBY answer with confidence and follow-up."""
    # Mandatory Rule: Personal claim status queries must refuse with 'I don't know'
    if is_personal_claim_query(question):
        return {
            "answer": (
                "I don't know. PMFBY official guideline records do not contain personal "
                "farmer claim approvals or live application statuses. Please check your "
                "application status directly on pmfby.gov.in (NCIP), through the Crop Insurance "
                "App, or by calling Krishi Rakshak Helpline 14447."
            ),
            "confidence": 0.0,
            "follow_up": "Would you like guidance on the 72-hour claim intimation procedure or grievance escalation to the DGRC?",
            "citations": [],
            "prompt_version": prompt_version,
            "provider": "policy-guard",
            "model": "grounding-safeguard",
        }

    records = context_records if context_records is not None else load_records()
    matches = smart_search(records, question, top_k=top_k)

    # Format context for prompt
    context_lines = []
    for idx, m in enumerate(matches, 1):
        context_lines.append(
            f"[{idx}] Topic: {m.get('rule_topic')} | Version: {m.get('og_version')} | "
            f"Rate/Timeline: {m.get('deadline_or_rate')} | Text: {m.get('rule_text')}"
        )
    context_str = "\n".join(context_lines) if context_lines else "No direct matching record found."

    # Load prompts
    system_prompt = load_prompt_file(SYSTEM_PROMPT_PATH)
    task_template = load_prompt_file(PROMPT_V1_PATH if prompt_version == "v1" else PROMPT_V2_PATH)
    user_prompt = task_template.replace("{context}", context_str).replace("{question}", question)

    provider, api_key, model = get_configured_provider()
    result: dict | None = None

    if provider == "groq" and api_key:
        try:
            result = _call_groq(api_key, model, system_prompt, user_prompt)
        except Exception as exc:
            logging.warning("Groq call failed (%s); falling back to rule engine.", exc)
    elif provider == "gemini" and api_key:
        try:
            result = _call_gemini(api_key, model, system_prompt, user_prompt)
        except Exception as exc:
            logging.warning("Gemini call failed (%s); falling back to rule engine.", exc)

    if not result or not isinstance(result, dict) or "answer" not in result:
        result = _offline_fallback(question, matches, prompt_version)
        provider = "offline-rule-engine"
        model = "pmfby-guidelines-v1"

    citations = [
        {
            "id": m["id"],
            "rule_topic": m["rule_topic"],
            "og_version": m["og_version"],
            "deadline_or_rate": m["deadline_or_rate"],
            "source_url": m["source_url"],
        }
        for m in matches
    ]

    return {
        "answer": str(result.get("answer", "")).strip(),
        "confidence": float(result.get("confidence", 0.9)),
        "follow_up": str(result.get("follow_up", "")).strip(),
        "citations": citations,
        "prompt_version": prompt_version,
        "provider": provider,
        "model": model,
    }
