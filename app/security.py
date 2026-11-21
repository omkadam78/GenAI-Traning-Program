"""Small defense-in-depth guards; not a claim of complete injection prevention."""

import json
import re
import unicodedata

MAX_QUESTION_CHARS = 2000
MAX_BODY_BYTES = 16 * 1024
SAFE_REJECTION = "Please ask a crop-insurance question without instructions to override safeguards or reveal private configuration."

_ATTACKS = [
    r"\b(?:ignore|disregard|override|forget)\b.{0,65}\b(?:instructions?|system|rules?|prompts?|safeguards?)\b",
    r"\b(?:reveal|print|dump|expose|show|return)\b.{0,65}\b(?:system\s*prompt|api[ _-]*keys?|credentials?|secret(?:s|\s+keys?)?)\b",
    r"\b(?:bypass|skip|disable)\b.{0,40}\b(?:approval|confirmation|safety|guardrails?|security)\b",
    r"\b(?:pretend|fabricate|invent)\b.{0,65}\b(?:approved|approval|claim\s+status|payment|citations?)\b",
    r"<\|(?:system|im_start|assistant)\|>|\[/?inst\]|</?context_data\s*>|\[system\]",
    r"(?:पिछल[ेी]|मागील).{0,25}(?:निर्देश|सूचना).{0,25}(?:भूल|अनदेखा|दुर्लक्ष)",
]
_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _ATTACKS]


class InputGuardError(ValueError):
    pass


def looks_like_injection(text: str) -> bool:
    scan = unicodedata.normalize("NFKC", text)
    scan = re.sub(r"[\u200b-\u200d\ufeff]", "", scan)
    return any(pattern.search(scan) for pattern in _PATTERNS)


def validate_question(question: str | None) -> None:
    if question is None:
        return
    if len(question) > MAX_QUESTION_CHARS:
        raise InputGuardError(f"Keep your question within {MAX_QUESTION_CHARS} characters.")
    if looks_like_injection(question):
        raise InputGuardError(SAFE_REJECTION)


def safe_evidence(records: list[dict]) -> list[dict]:
    """Drop an entire suspicious chunk so its text and citation stay aligned."""
    return [r for r in records if not looks_like_injection(json.dumps(r, ensure_ascii=False))]


def context_json(records: list[dict]) -> str:
    """Escape markup control characters inside JSON, including closing data tags."""
    return json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def validate_answer(answer: str, secrets: list[str]) -> None:
    if any(secret and len(secret) >= 12 and secret in answer for secret in secrets):
        raise InputGuardError("The answer failed the private-configuration check.")
    if re.search(r"\bgsk_[A-Za-z0-9_-]{20,}\b|\bAIza[A-Za-z0-9_-]{25,}\b", answer):
        raise InputGuardError("The answer failed the private-configuration check.")
