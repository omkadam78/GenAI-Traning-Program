"""Unified LLM provider interface for Groq and Gemini with FasalBima Sathi prompts.

Features:
1. Unified provider interface supporting Groq (OpenAI-compatible) and Google Gemini REST APIs.
2. Configurable primary provider with automatic secondary-provider fallback.
3. Bounded retries with exponential backoff for retryable errors (429 rate limit, 503, timeouts).
4. Immediate failure classification for authentication errors (401/403) and missing models (404).
5. Anti-prompt-injection grounding that treats retrieved documents strictly as untrusted data.
6. Honest tracking of provider_used, model_used, fallback_occurred, latency_ms, and token usage.
7. Explicit separation of real LLM responses from deterministic rule-engine outputs.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Optional

from dotenv import dotenv_values
import requests

from app.records import load_records
from app.smart_search import smart_search

ROOT = Path(__file__).resolve().parents[1]
# Read configuration per request. Do not mutate process environment at import time.

PROMPTS_DIR = ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"
PROMPT_V1_PATH = PROMPTS_DIR / "task_v1_concise.txt"
PROMPT_V2_PATH = PROMPTS_DIR / "task_v2_detailed.txt"

# Current official default models
GROQ_DEFAULT_MODEL = "openai/gpt-oss-20b"
GEMINI_DEFAULT_MODEL = "gemini-flash-latest"

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


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    pass


class LLMAuthenticationError(LLMError):
    """Raised when provider credentials are rejected (401/403)."""

    pass


class LLMModelNotFoundError(LLMError):
    """Raised when requested model is deprecated or unsupported (404)."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when provider rate limits are exhausted (429)."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when provider requests time out."""

    pass


def load_prompt_file(path: Path) -> str:
    """Load text prompt from file with UTF-8 encoding."""
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def is_personal_claim_query(question: str) -> bool:
    """Detect private individual claim or policy status queries."""
    q = (question or "").strip().casefold()
    return any(re.search(pat, q) for pat in OUT_OF_SCOPE_PATTERNS)


def get_llm_config() -> dict[str, Any]:
    """Load current LLM configuration and detect primary/fallback providers.

    Reads dynamically from environment to allow runtime key injection.
    """
    settings = {**dotenv_values(ROOT / ".env"), **os.environ}
    pref = str(settings.get("LLM_PROVIDER") or "groq").strip().lower()
    groq_key = str(settings.get("GROQ_API_KEY") or "").strip()
    gemini_key = str(settings.get("GEMINI_API_KEY") or "").strip()

    groq_model = str(settings.get("GROQ_MODEL") or GROQ_DEFAULT_MODEL).strip()
    gemini_model = str(settings.get("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL).strip()

    primary_provider: str
    primary_key: str
    primary_model: str

    fallback_provider: Optional[str] = None
    fallback_key: Optional[str] = None
    fallback_model: Optional[str] = None

    if pref == "offline":
        return {
            "mode": "offline",
            "primary_provider": "offline",
            "primary_key": "",
            "primary_model": "pmfby-offline-v1",
            "fallback_provider": None,
            "fallback_key": None,
            "fallback_model": None,
        }

    if pref == "gemini":
        primary_provider = "gemini"
        primary_key = gemini_key
        primary_model = gemini_model
        if groq_key:
            fallback_provider = "groq"
            fallback_key = groq_key
            fallback_model = groq_model
    else:  # default to groq
        primary_provider = "groq"
        primary_key = groq_key
        primary_model = groq_model
        if gemini_key:
            fallback_provider = "gemini"
            fallback_key = gemini_key
            fallback_model = gemini_model

    # If primary has no key, but secondary does, promote secondary to primary
    if not primary_key and fallback_key:
        primary_provider, fallback_provider = fallback_provider, None
        primary_key, fallback_key = fallback_key, None
        primary_model, fallback_model = fallback_model, None

    mode = "live" if primary_key else "offline"

    return {
        "mode": mode,
        "primary_provider": primary_provider,
        "primary_key": primary_key,
        "primary_model": primary_model,
        "fallback_provider": fallback_provider,
        "fallback_key": fallback_key,
        "fallback_model": fallback_model,
    }


def _call_groq_api(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 25.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Execute chat completion against Groq API with retries and exponential backoff."""
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
        "max_completion_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            status = resp.status_code

            if status == 200:
                body = resp.json()
                raw_text = body["choices"][0]["message"]["content"]
                usage = body.get("usage", {})
                return {
                    "raw_text": raw_text,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }

            if status in (401, 403):
                raise LLMAuthenticationError(
                    f"Groq API authentication failed (HTTP {status}): Check GROQ_API_KEY."
                )
            if status == 404:
                raise LLMModelNotFoundError(
                    f"Groq model '{model}' not found (HTTP 404): Check GROQ_MODEL."
                )

            # Retryable status codes (429 rate limit, 500, 502, 503, 504)
            if status in (429, 500, 502, 503, 504):
                retry_after = 1.0
                if "Retry-After" in resp.headers:
                    try:
                        retry_after = min(float(resp.headers["Retry-After"]), 4.0)
                    except Exception:
                        pass
                else:
                    retry_after = (2**attempt) * 0.5

                if attempt < max_retries:
                    time.sleep(retry_after)
                    continue

                if status == 429:
                    raise LLMRateLimitError(
                        f"Groq API rate limit exhausted after {max_retries} retries."
                    )
                raise LLMError(f"Groq service error (HTTP {status}) after retries.")

            # Other non-retryable 4xx
            raise LLMError(f"Groq API request failed with HTTP {status}: {resp.text}")

        except requests.exceptions.Timeout:
            last_error = LLMTimeoutError(f"Groq API request timed out after {timeout}s.")
            if attempt < max_retries:
                time.sleep((2**attempt) * 0.5)
                continue
            raise last_error
        except requests.exceptions.ConnectionError:
            last_error = LLMError("Groq network connection failed.")
            if attempt < max_retries:
                time.sleep((2**attempt) * 0.5)
                continue
            raise last_error

    if last_error:
        raise last_error
    raise LLMError("Groq request failed with unknown error.")


def _call_gemini_api(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 25.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Execute generateContent against Google Gemini REST API with retries."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "maxOutputTokens": 1200,
        },
    }

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            status = resp.status_code

            if status == 200:
                body = resp.json()
                candidates = body.get("candidates", [])
                if not candidates:
                    raise LLMError("No candidates returned by Gemini API.")
                raw_text = candidates[0]["content"]["parts"][0]["text"]
                usage_meta = body.get("usageMetadata", {})
                return {
                    "raw_text": raw_text,
                    "usage": {
                        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                        "total_tokens": usage_meta.get("totalTokenCount", 0),
                    },
                }

            if status in (400, 401, 403):
                err_text = resp.text
                if "API_KEY_INVALID" in err_text or status in (401, 403):
                    raise LLMAuthenticationError(
                        f"Gemini API authentication failed (HTTP {status}): Check GEMINI_API_KEY."
                    )
                # Other 400 (malformed prompt)
                raise LLMError(f"Gemini API bad request (HTTP 400): {err_text}")

            if status == 404:
                raise LLMModelNotFoundError(
                    f"Gemini model '{model}' not found (HTTP 404): Check GEMINI_MODEL."
                )

            # Retryable status codes (429 rate limit, 500, 503)
            if status in (429, 500, 503):
                retry_after = (2**attempt) * 0.5
                if attempt < max_retries:
                    time.sleep(retry_after)
                    continue
                if status == 429:
                    raise LLMRateLimitError(
                        f"Gemini API rate limit exhausted after {max_retries} retries."
                    )
                raise LLMError(f"Gemini service error (HTTP {status}) after retries.")

            raise LLMError(f"Gemini request failed with HTTP {status}: {resp.text}")

        except requests.exceptions.Timeout:
            last_error = LLMTimeoutError(f"Gemini API request timed out after {timeout}s.")
            if attempt < max_retries:
                time.sleep((2**attempt) * 0.5)
                continue
            raise last_error
        except requests.exceptions.ConnectionError:
            last_error = LLMError("Gemini network connection failed.")
            if attempt < max_retries:
                time.sleep((2**attempt) * 0.5)
                continue
            raise last_error

    if last_error:
        raise last_error
    raise LLMError("Gemini request failed with unknown error.")


def _parse_confidence(conf_val: Any) -> float:
    """Safely parse model confidence into a float between 0.0 and 1.0."""
    if isinstance(conf_val, (int, float)):
        return max(0.0, min(1.0, float(conf_val)))
    if isinstance(conf_val, str):
        v = conf_val.strip().lower()
        if v in ("high", "very high", "certain"):
            return 0.95
        if v in ("medium", "moderate"):
            return 0.75
        if v in ("low", "uncertain"):
            return 0.4
        try:
            return max(0.0, min(1.0, float(v)))
        except ValueError:
            return 0.9
    return 0.9


def _parse_llm_json(raw_text: str) -> dict[str, Any]:
    """Parse JSON from model response, stripping markdown fences or extracting JSON object."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    data = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except Exception:
                pass

    if isinstance(data, dict) and isinstance(data.get("answer"), str) and data["answer"].strip():
        return {
            "answer": str(data.get("answer", "")).strip(),
            "confidence": _parse_confidence(data.get("confidence", 0.9)),
            "follow_up": str(data.get("follow_up", "")).strip(),
        }

    raise LLMError("The AI service returned an invalid answer. Please try again.")


def _offline_fallback(question: str, matches: list[dict], prompt_version: str) -> dict[str, Any]:
    """Deterministic offline fallback grounded strictly in loaded PMFBY records."""
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
        answer = f"Under {ver}, {topic} specifies that {rule_text} [Key rate/deadline: {rate}]."
        follow_up = "Would you like help calculating your sum insured or verifying the 72-hour claim window?"
        confidence = 0.95
    else:
        answer = (
            f"According to {ver}:\n\n"
            f"1. **Policy Provision**: {topic} — {rule_text}\n"
            f"2. **Applicable Rate / Timeline**: {rate}\n"
            f"3. **Scope & Application**: Applicable to {top.get('applies_to', 'Notified crops/areas')}.\n\n"
            f"For localized calamities or post-harvest losses, remember that loss intimation is compulsory within 72 hours via the Crop Insurance App, helpline 14447, bank, or agriculture department."
        )
        follow_up = "Do you need the exact reporting channels or DLJC dispute resolution steps for your district?"
        confidence = 0.98

    # Pure arithmetic calculation grounding if query requests financial parameters
    q_low = question.lower()
    area_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ha|hectares?)", q_low)
    sof_m = re.search(
        r"(?:rs\.?|inr|₹)?\s*(\d{1,3}(?:,\d{3})*|\d{4,6})\s*(?:per\s+ha|/ha|sof)?", q_low
    )
    if (
        area_m
        and sof_m
        and (
            "premium" in q_low
            or "sum insured" in q_low
            or "scale of finance" in q_low
            or "hailstorm" in q_low
        )
    ):
        try:
            from app.tools import pmfby_premium

            area_val = float(area_m.group(1))
            sof_val = float(sof_m.group(1).replace(",", ""))
            crop_name = "soybean" if "soybean" in q_low else ("wheat" if "wheat" in q_low else None)
            calc_res = pmfby_premium(scale_of_finance=sof_val, area=area_val, crop=crop_name)
            answer += (
                f"\n\n**Financial Assessment**:\n"
                f"- **Sum Insured**: ₹{calc_res['sum_insured']:,.2f} ({area_val} ha × ₹{sof_val:,.2f}/ha)\n"
                f"- **Statutory Farmer Premium Share**: ₹{calc_res['farmer_premium']:,.2f} ({calc_res['farmer_rate_percent']}% rate)"
            )
        except Exception:
            pass

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
    allow_offline_fallback: bool = True,
    answer_language: str = "en",
) -> dict[str, Any]:
    """Generate a structured PMFBY answer grounded in retrieved context using Groq or Gemini.

    If real LLM keys are configured, executes real LLM inference with bounded retries and
    automatic secondary-provider fallback.
    """
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
            "fallback_occurred": False,
            "latency_ms": 0.0,
        }

    records = context_records if context_records is not None else load_records()
    # Preserve evidence order so [1], [2], ... identify the same sources the UI shows.
    matches = (
        list(records[:top_k])
        if context_records is not None
        else smart_search(records, question, top_k=top_k)
    )
    if not matches:
        return {
            "answer": "I don't know. I could not find supporting information in the official documents. Please ask a more specific PMFBY question.",
            "confidence": 0.0,
            "follow_up": "Which crop, season or insurance rule would you like help with?",
            "citations": [],
            "provider": "evidence-guard",
            "model": "none",
            "fallback_occurred": False,
        }

    # Citations metadata
    citations = [
        {
            "id": m.get("id"),
            "rule_topic": m.get("rule_topic"),
            "og_version": m.get("og_version"),
            "deadline_or_rate": m.get("deadline_or_rate"),
            "source_url": m.get("source_url"),
        }
        for m in matches
    ]

    # Format context with anti-injection data boundaries
    context_lines = []
    for idx, m in enumerate(matches, 1):
        context_lines.append(
            f"[{idx}] Topic: {m.get('rule_topic')} | Version: {m.get('og_version')} | "
            f"Rate/Timeline: {m.get('deadline_or_rate')} | Text: {m.get('rule_text')}"
        )
    raw_context = "\n".join(context_lines) if context_lines else "No direct matching record found."
    context_str = f"<context_data>\n{raw_context}\n</context_data>"

    # Load prompts
    system_prompt = load_prompt_file(SYSTEM_PROMPT_PATH)
    language_name = {"en": "English", "mr": "Marathi", "hi": "Hindi"}.get(
        answer_language, "English"
    )
    system_prompt += f"\nWrite the answer and follow_up in {language_name}. Keep numbers, citations, units and guideline versions unchanged. Use simple farmer-friendly words."
    task_template = load_prompt_file(PROMPT_V1_PATH if prompt_version == "v1" else PROMPT_V2_PATH)
    user_prompt = task_template.replace("{context}", context_str).replace("{question}", question)

    config = get_llm_config()
    mode = config["mode"]

    if mode == "offline":
        if not allow_offline_fallback:
            raise LLMError(
                "The answer service is not configured for live AI. Please ask the project administrator to check the API configuration."
            )
        result = _offline_fallback(question, matches, prompt_version)
        return {
            "answer": result["answer"],
            "confidence": result["confidence"],
            "follow_up": result["follow_up"],
            "citations": citations,
            "prompt_version": prompt_version,
            "provider": "deterministic-rule-engine",
            "model": "pmfby-offline-v1",
            "fallback_occurred": False,
            "latency_ms": 0.0,
        }

    # Live Mode: Attempt Primary Provider with Bounded Retries
    primary_prov = config["primary_provider"]
    primary_key = config["primary_key"]
    primary_model = config["primary_model"]

    fallback_prov = config.get("fallback_provider")
    fallback_key = config.get("fallback_key")
    fallback_model = config.get("fallback_model")

    t0 = time.perf_counter()
    primary_error: Optional[Exception] = None

    try:
        if primary_prov == "groq":
            res = _call_groq_api(primary_key, primary_model, system_prompt, user_prompt)
        else:
            res = _call_gemini_api(primary_key, primary_model, system_prompt, user_prompt)

        latency = (time.perf_counter() - t0) * 1000.0
        parsed = _parse_llm_json(res["raw_text"])

        return {
            "answer": parsed["answer"],
            "confidence": parsed["confidence"],
            "follow_up": parsed["follow_up"],
            "citations": citations,
            "prompt_version": prompt_version,
            "provider": primary_prov,
            "model": primary_model,
            "fallback_occurred": False,
            "latency_ms": round(latency, 1),
            "usage": res.get("usage", {}),
        }

    except Exception as exc:
        primary_error = exc
        logging.warning("Primary LLM (%s/%s) failed: %s", primary_prov, primary_model, exc)

    # Automatic Secondary Provider Fallback
    if fallback_prov and fallback_key and fallback_model:
        logging.info("Attempting secondary LLM fallback (%s/%s)...", fallback_prov, fallback_model)
        t_fb = time.perf_counter()
        try:
            if fallback_prov == "groq":
                res = _call_groq_api(fallback_key, fallback_model, system_prompt, user_prompt)
            else:
                res = _call_gemini_api(fallback_key, fallback_model, system_prompt, user_prompt)

            latency = (time.perf_counter() - t_fb) * 1000.0
            parsed = _parse_llm_json(res["raw_text"])

            return {
                "answer": parsed["answer"],
                "confidence": parsed["confidence"],
                "follow_up": parsed["follow_up"],
                "citations": citations,
                "prompt_version": prompt_version,
                "provider": fallback_prov,
                "model": fallback_model,
                "fallback_occurred": True,
                "latency_ms": round(latency, 1),
                "usage": res.get("usage", {}),
            }
        except Exception as fb_exc:
            logging.error("Secondary LLM fallback also failed: %s", fb_exc)
            # Both failed

    if not allow_offline_fallback:
        raise LLMError(
            "The AI answer service is temporarily unavailable. Please try again shortly. Your question was not answered by an offline substitute."
        )

    # Fallback to offline rule engine if live LLM is completely unavailable,
    # but HONESTLY identify provider as deterministic-rule-engine
    result = _offline_fallback(question, matches, prompt_version)
    return {
        "answer": result["answer"],
        "confidence": result["confidence"],
        "follow_up": result["follow_up"],
        "citations": citations,
        "prompt_version": prompt_version,
        "provider": "deterministic-rule-engine",
        "model": "pmfby-offline-v1",
        "fallback_occurred": True,
        "primary_error": str(primary_error),
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }
