"""Regression checks for general questions, live-only answers and simple farmer flows."""

from unittest.mock import patch
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from app.agent_loop import extract_premium_params
from app.llm import generate_chat_response, LLMError


def test_general_premium_question_is_not_a_calculation():
    assert not extract_premium_params("What are farmer premium rates under PMFBY?")[
        "is_calc_intent"
    ]
    assert extract_premium_params("Calculate soybean premium for 1.2 ha at scale of finance 49000")[
        "is_calc_intent"
    ]


def test_live_path_never_silently_returns_offline_template():
    with pytest.raises(LLMError, match="not configured"):
        generate_chat_response(
            "Explain premiums",
            context_records=[
                {
                    "id": 1,
                    "rule_topic": "Premiums",
                    "rule_text": "Premium rate is 2%.",
                    "source_url": "https://pmfby.gov.in/faq",
                }
            ],
            allow_offline_fallback=False,
        )


def test_malformed_model_output_is_not_displayed_as_an_answer():
    from app.llm import _parse_llm_json

    with pytest.raises(LLMError):
        _parse_llm_json("not valid JSON")
    assert (
        _parse_llm_json('{"answer":"Supported answer","confidence":0.8}')["answer"]
        == "Supported answer"
    )


def test_farmer_ui_has_no_developer_controls_and_keeps_required_flows():
    a = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "ui/app.py"), default_timeout=15
    ).run()
    assert not a.exception
    assert len(a.session_state.messages) == 0
    assert not a.radio
    a.segmented_control(key="section").set_value("Estimate premium").run()
    assert not a.exception
    assert a.selectbox(key="crop").value == "Choose a crop"
    a.segmented_control(key="section").set_value("Report crop loss").run()
    assert not a.exception
    assert a.date_input(key="loss_date").value is None
    assert a.time_input(key="loss_time").value is None


def test_live_clock_parses_real_offset():
    from ui.app import parse_iso_datetime

    assert parse_iso_datetime("2026-11-18T14:30:00+05:30").hour == 14


def test_general_rates_retrieve_all_three_categories():
    from app.tools import pmfby_knowledge_search

    with patch("app.tools.query_semantic", return_value=[]):
        hits = pmfby_knowledge_search("What are the farmer premium rates under PMFBY?")["hits"]
    assert len(hits) == 3
    assert all(h["page"] is None for h in hits)  # Do not invent PDF page numbers.
    assert any("rabi" in h["title"].lower() for h in hits)


def test_ui_premium_form_creates_backend_approval():
    a = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "ui/app.py"), default_timeout=15
    ).run()
    a.segmented_control(key="section").set_value("Estimate premium").run()
    a.selectbox(key="crop").select("Soybean")
    a.selectbox(key="season").select("Kharif")
    a.number_input(key="area").set_value(1.2)
    a.number_input(key="finance").set_value(49000.0)
    response = {
        "answer": "Calculation ID calc_test. Submit approved: true or approved: false.",
        "requires_approval": True,
        "pending_calculation": {
            "id": "calc_test",
            "params": {
                "crop": "soybean",
                "season": "kharif",
                "area": 1.2,
                "area_unit": "ha",
                "scale_of_finance": 49000,
                "scale_of_finance_unit": "per_ha",
            },
        },
    }
    with patch("requests.post") as post:
        post.return_value.ok = True
        post.return_value.json.return_value = response
        next(b for b in a.button if b.label == "Review my estimate").click().run()
    assert not a.exception
    assert a.session_state.pending_approval["id"] == "calc_test"
    assert a.button(key="approve")
    displayed = " ".join(m.value for m in a.markdown)
    assert "approved: true" not in displayed and "calc_test" not in displayed
    assert "Check the details below" in displayed
