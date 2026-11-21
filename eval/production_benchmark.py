"""Paired cache benchmark. --live uses real Groq; --mock is explicitly synthetic."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime
import json
import os
from pathlib import Path
import statistics
import time
from unittest.mock import MagicMock, patch
import uuid
from zoneinfo import ZoneInfo

from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.main import app
from app.production import ANSWER_CACHE

QUESTIONS = [
    "What are the farmer premium rates under PMFBY?",
    "What losses are covered by PMFBY?",
    "How do I report localized hailstorm damage under PMFBY?",
    "What is the post-harvest coverage window under PMFBY?",
    "Is enrolment in PMFBY voluntary?",
]


def run_benchmark(live=False, pause_seconds=0):
    ANSWER_CACHE.clear()
    client = TestClient(app)
    body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "Synthetic benchmark response [1].",
                            "confidence": 0.9,
                            "follow_up": "",
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
    }
    fake = MagicMock(status_code=200)
    fake.json.return_value = body
    rows = []
    with nullcontext() if live else patch("app.production.requests.post", return_value=fake):
        for number, question in enumerate(QUESTIONS, 1):
            if number > 1 and pause_seconds:
                time.sleep(pause_seconds)
            scope = f"benchmark-{uuid.uuid4().hex}"
            row = dict(case_id=f"P{number}", question=question)
            answers = []
            for label in ("uncached", "cached"):
                start = time.perf_counter()
                response = client.post(
                    "/agent",
                    json=dict(
                        query=question, thread_id=scope, request_id=uuid.uuid4().hex, language="en"
                    ),
                )
                result = response.json()
                metrics = result.get("metrics", {})
                row[label] = dict(
                    http_status=response.status_code,
                    client_ms=round((time.perf_counter() - start) * 1000, 2),
                    metrics=metrics,
                    provider=result.get("provider"),
                    model=result.get("model"),
                    citations=len(result.get("citations", [])),
                )
                answers.append(result.get("answer"))
            row["same_answer"] = answers[0] == answers[1]
            row["passed"] = bool(
                row["uncached"]["http_status"] == row["cached"]["http_status"] == 200
                and row["uncached"]["provider"] == "groq"
                and row["cached"]["metrics"].get("cache_status") == "HIT"
                and row["cached"]["metrics"].get("llm_calls") == 0
                and row["same_answer"]
            )
            rows.append(row)
        # Same text in another conversation must generate rather than reuse a cached answer.
        if pause_seconds:
            time.sleep(pause_seconds)
        isolated = client.post(
            "/agent",
            json=dict(
                query=QUESTIONS[0],
                thread_id=f"isolation-{uuid.uuid4().hex}",
                request_id=uuid.uuid4().hex,
            ),
        ).json()
    passed = [r for r in rows if r["passed"]]
    cold = [r["uncached"]["client_ms"] for r in passed]
    warm = [r["cached"]["client_ms"] for r in passed]
    median_cold = statistics.median(cold) if cold else None
    median_warm = statistics.median(warm) if warm else None
    return dict(
        mode="live_groq" if live else "deterministic_mock",
        measured_at=datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
        environment="local FastAPI TestClient; real retrieval; live provider only with --live",
        methodology="Five exact-repeat pairs; distinct request IDs; same conversation within each pair. First retrieval may include cold index/model loading. No end-user adoption or factual-accuracy metric is inferred.",
        sample_pairs=len(rows),
        pause_between_cases_seconds=pause_seconds,
        passed_pairs=len(passed),
        median_uncached_client_ms=median_cold,
        median_cached_client_ms=median_warm,
        observed_median_latency_reduction_percent=round(
            100 * (median_cold - median_warm) / median_cold, 2
        )
        if median_cold
        else None,
        known_uncached_tokens=sum(
            r["uncached"]["metrics"].get("known_total_tokens", 0) for r in passed
        ),
        cached_provider_calls=sum(r["cached"]["metrics"].get("llm_calls", 0) for r in passed),
        scope_isolation_passed=isolated.get("metrics", {}).get("cache_status") == "MISS",
        cases=rows,
    )


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--mock", action="store_true")
    parser.add_argument("--env-file", help="Ignored local file; never printed or copied")
    parser.add_argument("--output", default="eval/production_benchmark.json")
    parser.add_argument(
        "--pause-seconds",
        type=float,
        help="Pause between cases (live default 35s; mock default 0).",
    )
    args = parser.parse_args()
    if args.env_file:
        values = dotenv_values(args.env_file)
        for key in ("GROQ_API_KEY", "GROQ_MODEL"):
            if values.get(key):
                os.environ[key] = values[key]
    os.environ["LLM_PROVIDER"] = "groq"
    os.environ["GEMINI_API_KEY"] = ""  # Measure one provider; do not mix unverified fallback.
    if args.mock:
        os.environ["GROQ_API_KEY"] = "gsk_synthetic_benchmark_never_a_real_key"
    elif not os.environ.get("GROQ_API_KEY"):
        parser.error("Live benchmark needs GROQ_API_KEY in the environment or ignored --env-file")
    pause = args.pause_seconds if args.pause_seconds is not None else (35 if args.live else 0)
    if not 0 <= pause <= 60:
        parser.error("pause-seconds must be between 0 and 60")
    result = run_benchmark(live=args.live, pause_seconds=pause)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=True, indent=2)
    )
    if result["passed_pairs"] != result["sample_pairs"] or not result["scope_isolation_passed"]:
        raise SystemExit("A benchmark assertion failed; inspect the retained results.")


if __name__ == "__main__":
    main()
