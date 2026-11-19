"""Day 11: meaningful offline API, tool, grounding and multilingual regressions."""

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from streamlit.testing.v1 import AppTest

from app.language import localize_result, numeric_facts, prepare_query
from app.llm import LLMError, generate_chat_response
from app.main import app, AgentRequest, IdempotencyManager
from app.tools import pmfby_premium
from ui.i18n import STRINGS, translate

client = TestClient(app)
CONTEXT = [
    {
        "id": 1,
        "rule_topic": "Kharif premium",
        "rule_text": "Farmer share is capped at 2%.",
        "source_url": "https://pmfby.gov.in/faq",
        "og_version": "Revamped OG",
    }
]


def test_ask_uses_fake_llm_and_returns_sources():
    chunks = [
        {
            "chunk_id": "test_1",
            "score": 0.9,
            "text": "Loss reporting window is 72 hours.",
            "source": "https://pmfby.gov.in/faq",
            "page": 1,
            "title": "Loss reporting",
        }
    ]
    with (
        patch("app.rag.query_semantic", return_value=chunks),
        patch(
            "app.rag.generate_chat_response",
            return_value={
                "answer": "Report within 72 hours.",
                "provider": "fake-test",
                "confidence": 0.8,
            },
        ),
    ):
        result = client.post("/ask", json={"question": "When should I report crop loss?"})
    assert result.status_code == 200
    assert result.json()["answered"]
    assert result.json()["provider"] == "fake-test"
    assert result.json()["citations"][0]["source"] == "https://pmfby.gov.in/faq"


def test_irrelevant_retrieval_never_reaches_llm():
    with (
        patch("app.rag.query_semantic", return_value=[{"score": 0.01}]),
        patch("app.rag.generate_chat_response") as model,
    ):
        result = client.post("/ask", json={"question": "Who won the cricket match?"})
    assert not result.json()["answered"]
    model.assert_not_called()


@pytest.mark.parametrize("area", [0, -1, True, float("nan"), float("inf")])
def test_premium_rejects_invalid_area(area):
    with pytest.raises(ValueError):
        pmfby_premium(49000, area, crop="soybean")


def test_missing_rate_evidence_is_not_replaced_with_defaults():
    with patch("app.tools.load_records", return_value=[]):
        with pytest.raises(ValueError):
            pmfby_premium(49000, 1.2, crop="soybean")


def test_private_claim_status_is_refused_without_provider_call():
    with patch("app.llm._call_groq_api") as model:
        result = client.post(
            "/agent",
            json={
                "query": "Has my PMFBY claim been approved?",
                "thread_id": uuid.uuid4().hex,
                "language": "mr",
            },
        )
    assert result.status_code == 200
    assert "मला माहीत नाही" in result.json()["answer"]
    model.assert_not_called()


def test_translated_query_preserves_numeric_facts():
    config = dict(mode="live", primary_provider="groq", primary_key="test", primary_model="test")
    response = {
        "raw_text": json.dumps({"answer": "Calculate soybean premium for 1.2 ha at finance 49000."})
    }
    with (
        patch("app.language.get_llm_config", return_value=config),
        patch("app.language._call_groq_api", return_value=response),
    ):
        translated = prepare_query("१.२ हेक्टर सोयाबीनसाठी ४९००० वित्तमानाचा हप्ता काढा")
    assert numeric_facts(translated) == ["1.2", "49000"]


def test_translation_cannot_change_land_area():
    config = dict(mode="live", primary_provider="groq", primary_key="test", primary_model="test")
    with (
        patch("app.language.get_llm_config", return_value=config),
        patch(
            "app.language._call_groq_api",
            return_value={"raw_text": json.dumps({"answer": "Premium for 12 ha."})},
        ),
    ):
        with pytest.raises(LLMError):
            prepare_query("१.२ हेक्टर हप्ता")


def test_selected_language_reaches_real_answer_prompt():
    config = dict(mode="live", primary_provider="groq", primary_key="test", primary_model="test")
    with (
        patch("app.llm.get_llm_config", return_value=config),
        patch(
            "app.llm._call_groq_api",
            return_value={"raw_text": json.dumps({"answer": "हप्ता २% आहे.", "confidence": 0.8})},
        ) as call,
    ):
        result = generate_chat_response(
            "What is the premium?",
            context_records=CONTEXT,
            answer_language="mr",
            allow_offline_fallback=False,
        )
    assert "Marathi" in call.call_args.args[2]
    assert result["answer"] == "हप्ता २% आहे."


def test_localized_calculation_keeps_exact_tool_amounts():
    calc = pmfby_premium(49000, 1.2, crop="soybean")
    result = localize_result(
        {"status": "completed", "tool_calls": [{"tool": "pmfby_premium", "output": calc}]}, "hi"
    )
    assert "1,176.00" in result["answer"]
    assert "58,800.00" in result["answer"]
    assert result["citations"][0]["source"].startswith("https://pmfby.gov.in/")


def test_language_is_part_of_idempotency_identity():
    key = uuid.uuid4().hex
    payload = {
        "query": "Has my PMFBY claim been approved?",
        "thread_id": uuid.uuid4().hex,
        "request_id": key,
    }
    assert client.post("/agent", json=payload).status_code == 200
    assert client.post("/agent", json={**payload, "language": "hi"}).status_code == 409


def test_in_flight_request_id_cannot_be_reused_for_a_different_calculation():
    manager = IdempotencyManager()
    original = AgentRequest(query="Calculate premium for 1 ha", thread_id="test")
    changed = AgentRequest(query="Calculate premium for 10 ha", thread_id="test")
    assert manager.check_or_register("same-key", original) == (None, False)
    assert manager.check_or_register("same-key", original) == (None, True)
    with pytest.raises(HTTPException) as error:
        manager.check_or_register("same-key", changed)
    assert error.value.status_code == 409


@pytest.mark.parametrize("language", ["mr", "hi"])
def test_farmer_forms_and_navigation_render_in_selected_language(language):
    from pathlib import Path

    test = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "ui/app.py"), default_timeout=20
    ).run()
    test.selectbox(key="language").set_value(language).run()
    assert not test.exception
    assert translate("A helping hand for your harvest", language) in [t.value for t in test.title]
    test.segmented_control(key="section").set_value("Estimate premium").run()
    assert test.selectbox(key="crop").label == translate("Your crop", language)
    test.segmented_control(key="section").set_value("Report crop loss").run()
    assert not test.exception
    assert test.date_input(key="loss_date").label == translate(
        "When did the loss happen?", language
    )


def test_translation_catalog_has_no_blank_entries():
    assert all(marathi.strip() and hindi.strip() for marathi, hindi in STRINGS.values())
