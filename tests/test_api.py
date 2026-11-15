"""Tests for Day 3 ingestion, Day 4 API, Day 5 questions, Day 6 LLM, Day 7 Semantic Search, and Day 8 RAG."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from analysis.explore import analyze_records
from app.chunking import get_all_chunks
from app.ingest import extract_records
from app.main import app
from app.rag import ask_rag
from app.records import load_records
from app.smart_search import smart_search
from app.vectorstore import query_semantic

client = TestClient(app)


def test_ingest_parses_raw_sources():
    records = extract_records()
    assert len(records) >= 15
    required = {
        "id",
        "rule_topic",
        "rule_text",
        "og_version",
        "applies_to",
        "deadline_or_rate",
        "source_url",
    }
    for row in records:
        assert required.issubset(row.keys())
        assert all(str(row[k]).strip() for k in required)


def test_smart_search_ranks_hailstorm_and_premium():
    records = load_records()
    hail_hits = smart_search(records, "hailstorm individual farm", top_k=3)
    assert hail_hits
    assert hail_hits[0]["score"] > 0
    assert any("hailstorm" in r["rule_text"].lower() or "hailstorm" in r["rule_topic"].lower() for r in hail_hits)

    prem_hits = smart_search(records, "kharif soybean oilseed premium", top_k=3)
    assert prem_hits
    assert any("2.0%" in r["deadline_or_rate"] or "2%" in r["rule_text"] for r in prem_hits)


def test_explore_returns_three_facts():
    stats = analyze_records()
    assert stats["total_records"] >= 15
    assert stats["records_with_numeric_deadline_or_rate"] >= 5
    assert len(stats["source_counts"]) >= 2


def test_api_health_and_records():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["product"] == "FasalBima Sathi"
    assert body["records_count"] >= 15

    res_list = client.get("/records?limit=5")
    assert res_list.status_code == 200
    assert len(res_list.json()["records"]) == 5

    res_one = client.get("/records/1")
    assert res_one.status_code == 200
    assert res_one.json()["id"] == 1

    res_missing = client.get("/records/99999")
    assert res_missing.status_code == 404


def test_api_search_and_questions_including_q6():
    res_search = client.get("/search", params={"q": "72 hours intimation", "limit": 3})
    assert res_search.status_code == 200
    assert res_search.json()["count"] >= 1

    q1 = client.post(
        "/questions",
        json={"question": "What premium do I pay for soybean crop insurance in kharif?"},
    )
    assert q1.status_code == 200
    assert q1.json()["answered"] is True
    assert q1.json()["citations"]

    # Q6 from project card must get an honest "I don't know"
    q6 = client.post(
        "/questions",
        json={"question": "Has my PMFBY claim for kharif 2025 been approved?"},
    )
    assert q6.status_code == 200
    q6_body = q6.json()
    assert q6_body["answered"] is False
    assert "i don't know" in q6_body["answer"].lower()


def test_day5_questions_file_has_10_questions_and_q6():
    q_file = Path(__file__).resolve().parents[1] / "eval" / "questions.json"
    questions = json.loads(q_file.read_text(encoding="utf-8"))
    assert len(questions) == 10
    q6 = next(q for q in questions if q["id"] == "Q6")
    assert q6["answerable_from_data"] is False


def test_day6_chat_endpoint_v1_and_v2():
    res_v1 = client.post(
        "/chat",
        json={
            "message": "What premium do I pay for soybean crop insurance in kharif?",
            "prompt_version": "v1",
        },
    )
    assert res_v1.status_code == 200
    body1 = res_v1.json()
    assert "answer" in body1 and body1["answer"]
    assert "confidence" in body1 and isinstance(body1["confidence"], (int, float))
    assert "follow_up" in body1 and body1["follow_up"]
    assert body1["prompt_version"] == "v1"

    res_v2 = client.post(
        "/chat",
        json={
            "message": "Hailstorm hit my soybean field. What is the deadline to inform?",
            "prompt_version": "v2",
        },
    )
    assert res_v2.status_code == 200
    body2 = res_v2.json()
    assert "answer" in body2 and body2["answer"]
    assert "72 hours" in body2["answer"].lower() or "hailstorm" in body2["answer"].lower()
    assert "confidence" in body2 and body2["confidence"] > 0.0
    assert "follow_up" in body2
    assert body2["prompt_version"] == "v2"


def test_day6_chat_endpoint_refuses_q6():
    res = client.post(
        "/chat",
        json={
            "message": "Has my PMFBY claim for kharif 2025 been approved?",
            "prompt_version": "v2",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "i don't know" in body["answer"].lower()
    assert body["confidence"] == 0.0
    assert "follow_up" in body


def test_day6_files_and_git_safety():
    root = Path(__file__).resolve().parents[1]
    example = root / ".env.example"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "GROQ_API_KEY" in text
    assert "GEMINI_API_KEY" in text

    prompts_dir = root / "prompts"
    assert (prompts_dir / "system_prompt.txt").is_file()
    assert (prompts_dir / "task_v1_concise.txt").is_file()
    assert (prompts_dir / "task_v2_detailed.txt").is_file()

    compare_md = root / "eval" / "prompt_compare.md"
    assert compare_md.is_file()
    compare_text = compare_md.read_text(encoding="utf-8")
    for i in range(1, 11):
        assert f"Q{i}:" in compare_text


def test_day7_chunking_and_semantic_search():
    # Verify chunk extraction has required metadata (source, page, title)
    chunks = get_all_chunks(include_full_pdfs=False)
    assert len(chunks) >= 20
    sample = chunks[0]
    assert "id" in sample and sample["id"]
    assert "text" in sample and sample["text"]
    assert "source" in sample and sample["source"]
    assert "page" in sample and isinstance(sample["page"], int)
    assert "title" in sample and sample["title"]

    # Test Chroma vectorstore retrieval
    hits = query_semantic("hailstorm loss intimation timeline", top_k=3)
    assert len(hits) >= 1
    assert "chunk_id" in hits[0]
    assert "score" in hits[0]
    assert "source" in hits[0]
    assert "page" in hits[0]

    # Test GET /search/semantic endpoint
    res = client.get("/search/semantic", params={"q": "soybean kharif premium", "limit": 3})
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    assert len(data["results"]) <= 3

    # Test eval/search_results.md exists and covers 10 questions
    search_md = Path(__file__).resolve().parents[1] / "eval" / "search_results.md"
    assert search_md.is_file()
    content = search_md.read_text(encoding="utf-8")
    for i in range(1, 11):
        assert f"Q{i}:" in content


def test_day8_rag_ask_and_eval_suite():
    # Test POST /ask on an answerable question
    res_ans = client.post(
        "/ask",
        json={"question": "What premium do I pay for soybean crop insurance in kharif?", "top_k": 3},
    )
    assert res_ans.status_code == 200
    body = res_ans.json()
    assert body["answered"] is True
    assert "answer" in body and body["answer"]
    assert "citations" in body and len(body["citations"]) >= 1
    citation = body["citations"][0]
    assert "source" in citation
    assert "page" in citation

    # Test POST /ask strictly refuses Q6
    res_q6 = client.post(
        "/ask",
        json={"question": "Has my PMFBY claim for kharif 2025 been approved?", "top_k": 3},
    )
    assert res_q6.status_code == 200
    q6_data = res_q6.json()
    assert q6_data["answered"] is False
    assert "i don't know" in q6_data["answer"].lower()
    assert q6_data["confidence"] == 0.0

    # Test POST /ask strictly refuses Q15 (bank account inquiry)
    res_q15 = client.post(
        "/ask",
        json={"question": "Can you check if my compensation payment has reached my State Bank of India account?", "top_k": 3},
    )
    assert res_q15.status_code == 200
    assert res_q15.json()["answered"] is False
    assert "i don't know" in res_q15.json()["answer"].lower()

    # Test eval/eval_set.json has 15 rows
    root = Path(__file__).resolve().parents[1]
    eval_set = json.loads((root / "eval" / "eval_set.json").read_text(encoding="utf-8"))
    assert len(eval_set) == 15

    # Test README contains RAG evaluation winner table
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "RAG Evaluation: 2 Configurations Comparison" in readme
    assert "Config A" in readme
    assert "Config B" in readme
    assert "WINNER" in readme
