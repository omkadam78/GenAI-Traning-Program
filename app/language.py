"""Language handling keeps translated queries separate from deterministic tool inputs."""

from __future__ import annotations

import re
import unicodedata

from app.llm import LLMError, _call_gemini_api, _call_groq_api, _parse_llm_json, get_llm_config

from app.security import validate_question

LANGUAGES = {"en": "English", "mr": "Marathi", "hi": "Hindi"}


def numeric_facts(text: str) -> list[str]:
    normalized = "".join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)
    return sorted(re.findall(r"\d+(?:[,.]\d+)*", normalized.replace(",", "")))


def prepare_query(question: str | None) -> str | None:
    """Translate Devanagari input for English retrieval; refuse changed numeric facts."""
    validate_question(question)
    if not question or not re.search(r"[\u0900-\u097f]", question):
        return question
    config = get_llm_config()
    if config["mode"] != "live":
        raise LLMError("Language help needs the answer service. Please try again shortly.")
    prompt = (
        "Translate this farmer question into English for document search. Do not answer it. "
        "Preserve every number, unit, date, time, negation and crop. Do not infer missing facts. "
        "Return JSON with answer (the translation), confidence and follow_up (empty)."
    )
    for provider, key, model in [
        (config["primary_provider"], config["primary_key"], config["primary_model"]),
        (config.get("fallback_provider"), config.get("fallback_key"), config.get("fallback_model")),
    ]:
        if not provider or not key:
            continue
        try:
            call = _call_groq_api if provider == "groq" else _call_gemini_api
            result = _parse_llm_json(call(key, model, prompt, question)["raw_text"])["answer"]
            if numeric_facts(result) != numeric_facts(question):
                raise LLMError("The translation changed a number. Please rephrase your question.")
            return result
        except LLMError:
            continue
    raise LLMError("We could not translate this question safely. Please try again.")


def localize_result(result: dict, language: str) -> dict:
    """Translate deterministic states without allowing an LLM to recalculate amounts."""
    if language == "en":
        return result
    result = dict(result)
    mr = language == "mr"
    if result.get("requires_approval"):
        result["answer"] = (
            "खालील पीक, क्षेत्र आणि वित्तमान तपासा. तुमच्या संमतीनंतरच अंदाज काढला जाईल."
            if mr
            else "नीचे फसल, क्षेत्र और वित्तमान जाँचें। आपकी पुष्टि के बाद ही अनुमान निकलेगा।"
        )
    elif result.get("status") == "cancelled":
        result["answer"] = (
            "गणना रद्द केली. कोणतीही रक्कम भरलेली नाही."
            if mr
            else "गणना रद्द की गई। कोई भुगतान नहीं हुआ है।"
        )
    elif result.get("intent") == "refusal":
        result["answer"] = (
            "मला माहीत नाही. हे अ‍ॅप तुमच्या वैयक्तिक दाव्याची मंजुरी किंवा बँक खात्यातील पैसे तपासू शकत नाही. अधिकृत PMFBY पोर्टल किंवा विमा कंपनीशी संपर्क करा."
            if mr
            else "मुझे नहीं पता। यह ऐप आपके निजी दावे की मंजूरी या बैंक भुगतान नहीं जाँच सकता। आधिकारिक PMFBY पोर्टल या बीमा कंपनी से संपर्क करें।"
        )
    else:
        calc = next(
            (
                c.get("output")
                for c in result.get("tool_calls", [])
                if c.get("tool") == "pmfby_premium"
            ),
            None,
        )
        if calc:
            title = "शेतकरी हप्त्याचा कमाल अंदाज" if mr else "किसान प्रीमियम का अधिकतम अनुमान"
            if not calc.get("is_estimated_maximum"):
                title = "दिलेल्या दरानुसार हप्ता" if mr else "दिए गए दर के अनुसार प्रीमियम"
            result["answer"] = (
                f"**{title}: ₹{calc['farmer_premium']:,.2f}**\n\n"
                f"- {'विम्याची रक्कम' if mr else 'बीमित राशि'}: ₹{calc['sum_insured']:,.2f}\n"
                f"- {'हप्ता दर' if mr else 'प्रीमियम दर'}: {calc['farmer_rate_percent']}%\n\n"
                + (
                    "हा गणनेचा अंदाज आहे; विमा खरेदी किंवा दावा सादर झालेला नाही."
                    if mr
                    else "यह गणना का अनुमान है; बीमा खरीदा या दावा जमा नहीं किया गया है."
                )
            )
            reference = calc.get("rule_reference", {})
            if reference.get("source_url"):
                result["citations"] = [
                    dict(
                        source=reference["source_url"],
                        title=reference.get("rule_topic", "PMFBY"),
                        page=None,
                    )
                ]
            deadline = next(
                (
                    c.get("output")
                    for c in result.get("tool_calls", [])
                    if c.get("tool") == "pmfby_claim_deadline_check"
                ),
                None,
            )
            if deadline:
                result["answer"] += (
                    "\n\n"
                    + ("नुकसान कळवण्याची अंतिम वेळ: " if mr else "नुकसान की सूचना का अंतिम समय: ")
                    + deadline["deadline_timestamp"]
                )
        elif result.get("status") in ("clarification_needed", "error", "rejected"):
            result["answer"] = (
                (
                    "माहिती अपुरी आहे किंवा सेवा उपलब्ध नाही. पीक, हंगाम, क्षेत्र, वित्तमान आणि तारीख/वेळ तपासा. मूळ तपशील:"
                    if mr
                    else "जानकारी अधूरी है या सेवा उपलब्ध नहीं है। फसल, मौसम, क्षेत्र, वित्तमान और तारीख/समय जाँचें। मूल विवरण:"
                )
                + "\n\n"
                + result.get("answer", "")
            )
    return result
