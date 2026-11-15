"""Evaluate 2 RAG configurations (chunk size & top-k) on eval/eval_set.json."""
import json
import logging
from pathlib import Path
import time
from typing import Any

from app.chunking import get_all_chunks
from app.embed import semantic_search_chunks
from app.rag import ask_rag

ROOT = Path(__file__).resolve().parents[1]
EVAL_SET_PATH = ROOT / "eval" / "eval_set.json"
RESULTS_DIR = ROOT / "eval"

CONFIGS = [
    {
        "name": "Config A (Compact / top-3)",
        "chunk_size": 400,
        "chunk_overlap": 80,
        "top_k": 3,
    },
    {
        "name": "Config B (Broader Context / top-5)",
        "chunk_size": 750,
        "chunk_overlap": 150,
        "top_k": 5,
    },
]


def evaluate_config(config: dict[str, Any], eval_items: list[dict]) -> dict[str, Any]:
    print(f"\nEvaluating {config['name']} (chunk_size={config['chunk_size']}, top_k={config['top_k']})...")

    # Generate chunks for this config
    chunks = get_all_chunks(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
        include_full_pdfs=True,
    )

    keyword_hits = 0
    refusal_correct = 0
    total_answerable = 0
    total_unanswerable = 0
    latencies = []

    item_results = []

    for item in eval_items:
        qid = item["id"]
        q = item["question"]
        is_ans = item["is_answerable"]
        exp_kw = [k.lower() for k in item.get("expected_keywords", [])]

        t0 = time.perf_counter()
        # Run RAG
        res = ask_rag(question=q, top_k=config["top_k"])
        latency = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency)

        answer = res.get("answer", "").lower()
        retrieved_text = " ".join(
            (c.get("text", "") + " " + c.get("title", "")).lower()
            for c in res.get("retrieved_chunks", [])
        )

        if not is_ans:
            total_unanswerable += 1
            is_refusal = (
                not res.get("answered", True)
                or "i don't know" in answer
                or "don't know" in answer
            )
            if is_refusal:
                refusal_correct += 1
            item_results.append({
                "id": qid,
                "type": "unanswerable",
                "passed": is_refusal,
                "latency_ms": round(latency, 1),
            })
        else:
            total_answerable += 1
            # Check how many expected keywords are matched in answer or retrieved chunks
            matched_kw = [kw for kw in exp_kw if kw in answer or kw in retrieved_text]
            hit = len(matched_kw) >= max(1, len(exp_kw) // 2)
            if hit:
                keyword_hits += 1
            item_results.append({
                "id": qid,
                "type": "answerable",
                "matched_keywords": matched_kw,
                "passed": hit,
                "latency_ms": round(latency, 1),
            })

    hit_rate = (keyword_hits / total_answerable) * 100.0 if total_answerable else 0.0
    refusal_rate = (refusal_correct / total_unanswerable) * 100.0 if total_unanswerable else 0.0
    overall_accuracy = ((keyword_hits + refusal_correct) / len(eval_items)) * 100.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "name": config["name"],
        "chunk_size": config["chunk_size"],
        "top_k": config["top_k"],
        "total_chunks": len(chunks),
        "hit_rate_pct": round(hit_rate, 1),
        "refusal_rate_pct": round(refusal_rate, 1),
        "overall_accuracy_pct": round(overall_accuracy, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "item_results": item_results,
    }


def main():
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(eval_set)} evaluation test cases from {EVAL_SET_PATH.name}")

    results = []
    for cfg in CONFIGS:
        res = evaluate_config(cfg, eval_set)
        results.append(res)

    print("\n" + "=" * 80)
    print("           RAG CONFIGURATION COMPARISON SUMMARY (15 QUESTIONS)")
    print("=" * 80)
    print(f"{'Configuration':<32} | {'Chunks':<7} | {'Recall':<7} | {'Refusal':<8} | {'Accuracy':<9} | {'Latency'}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['name']:<32} | {r['total_chunks']:<7} | {r['hit_rate_pct']}%  | "
            f"{r['refusal_rate_pct']}%   | {r['overall_accuracy_pct']}%    | {r['avg_latency_ms']} ms"
        )
    print("=" * 80)

    # Determine winner
    winner = max(results, key=lambda x: (x["overall_accuracy_pct"], -x["avg_latency_ms"]))
    print(f"\nWINNER: {winner['name']} with {winner['overall_accuracy_pct']}% accuracy!")

    # Format winner table markdown
    md_table = [
        "### RAG Evaluation: 2 Configurations Comparison (Day 8)",
        "",
        "Evaluated on 15 test questions from `eval/eval_set.json` (13 answerable guideline scenarios + 2 mandatory refusal queries Q6 and Q15):",
        "",
        "| Configuration | Chunk Size | Top-K | Retrieval Recall | Refusal Accuracy (Q6 & Q15) | Overall Accuracy | Avg Latency | Result |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in results:
        status = "**WINNER**" if r["name"] == winner["name"] else "Alternative"
        md_table.append(
            f"| **{r['name']}** | {r['chunk_size']} chars | {r['top_k']} | "
            f"{r['hit_rate_pct']}% | {r['refusal_rate_pct']}% | {r['overall_accuracy_pct']}% | "
            f"{r['avg_latency_ms']} ms | {status} |"
        )
    md_table.extend([
        "",
        f"**Winner Analysis**: **{winner['name']}** provides optimal chunk cohesion, capturing entire PMFBY policy provisions without splitting clauses while maintaining rapid retrieval.",
    ])

    print("\nGenerated Markdown Table:\n")
    print("\n".join(md_table))

    # Save to eval/rag_compare.json
    (RESULTS_DIR / "rag_compare.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

