# Read the project in this order

| Question | Start here |
|---|---|
| What is the product and how do I run it? | Root `README.md` |
| What does the farmer see? | `ui/app.py`, `ui/i18n.py`, `ui/assets/` |
| What is the API contract? | `app/main.py`; running `/docs` or public `/api/docs` |
| How are records built? | `app/fetch.py`, `app/ingest.py`, `app/models.py`, `data/raw/manifest.json` |
| Where are retrieval and evidence? | `app/chunking.py`, `app/embed.py`, `app/vectorstore.py`, `app/rag.py` |
| Who decides knowledge vs arithmetic? | `app/graph.py`, `app/agent_loop.py`, `app/tools.py` |
| How are live providers called? | `app/llm.py`, `app/language.py`, `prompts/` |
| Where are cache, metrics and input guards? | `app/production.py`, `app/security.py` |
| What do the evaluation numbers mean? | `eval/run_eval.py`, `eval/rag_compare.json`, `eval/production_benchmark.py`, `docs/production_notes.md` |
| What prevents regressions? | `tests/`, `pyproject.toml`, `.github/workflows/ci.yml` |
| What runs in production? | `Dockerfile`, `docker-compose.yml`, `deploy/serve.py`, `deploy/smoke.py`, `render.yaml` |
| What can I claim in a resume/viva? | `docs/resume.md`, `docs/interview.md` |
| How do I present/recover? | `docs/demo_runbook.md`, `PROGRESS.md` |

## Evidence, not inflated claims

The corpus contains official documents; that does not establish they are the latest
applicable state/season rules. Tests are controlled checks; they do not prove perfect
security or accuracy. The 78.46% latency reduction is from five local live-provider
repeat pairs, not an adoption study. The public app provides guidance and estimates,
not insurer-authorized transactions or claim status. The Android preview is a separate
experiment and is not part of this tagged training release.

## Release scope

Days 1–13 were reviewer-accepted, with seven stars as of 22 November 2026. Day 14
adds interview preparation, an auditable closeout and demo readiness. Day 15 remains
the student's final test/live demo/Q&A. Public-world product rollout needs updated
source verification, user research, appropriate data handling and operational hardening;
those are future product work, not hidden completed features.
