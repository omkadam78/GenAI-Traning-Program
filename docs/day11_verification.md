# Day 11 verification — 19 November 2026

Owner: Om Kiran Kadam / 2124UDSM2013. Project: FasalBima Sathi (SJ-07).

## Required training work

- Pytest covers records, search, health and /ask with fake LLM output. The full
  suite also covers arithmetic, approval isolation, citations, refusal, feedback,
  language handling and UI navigation. No real API key is needed for tests.
- `python -m pytest -q`: **76 passed in 89.92s**, on the local Python environment.
- `python -m ruff check .`: passes. `python -m ruff format --check .`: passes.
- Dockerfile, .dockerignore and docker-compose.yml supplied. Image runs as a
  non-root user. API and UI use separate services, internal networking and health
  checks. Keys and local feedback are excluded from the image context.
- Official standalone Docker Compose validated the configuration with
  `--env-file .env.example config --quiet`.
- Docker engine/Desktop is absent on this machine. The image has **not** been built
  or run here; `docker compose up --build` and tests inside the image remain pending.
  Configuration validation is not evidence of a successful container runtime.

## Additional farmer experience work

- Original vector crop/shield mark, wordmark and PNG favicon in ui/assets.
- English, Marathi and Hindi interface labels; selected-language live answers.
- Marathi/Hindi query translation for English retrieval. Changed numeric facts
  cause rejection; this check does not establish full translation correctness.
- Premium and deadline arithmetic remain Python tool results. Calculations still
  require explicit approval. No payment or claim submission feature was added.
- Reporting preparation checklist and UTF-8 text download using actual clock data.
- Existing personal-data refusal, official sources and feedback isolation retained.
- Request identity includes selected language; conflicting in-flight payloads are
  rejected rather than being executed or replayed under the same request ID.

## Live and visual checks

A Marathi question returned HTTP 200 with actual Groq inference and five source
citations. A glossary correction fixed an observed soybean translation in a
follow-up. This is a spot check, not a language accuracy benchmark. Gemini fallback
generation remains unverified. No RAG accuracy improvement is claimed from this work.

The running Streamlit interface was visually checked in English and Marathi,
including translated premium inputs. Screenshots are in docs/images/day11-*.jpg.
The matched local verification pair uses API 8050 and UI 8550. Default local and
Docker instructions use API 8000 and UI 8501.

## Limits relevant to review

Conversation checkpoints and idempotency storage remain in process memory. Restarting
loses conversation/approval state; the local app is not a multi-worker production
service. Official guideline coverage and actual claim decisions remain the insurer's
and state's responsibility. Earlier checkpoint tags are not moved by Day 11 work.
