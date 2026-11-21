# Day 13 verification — 21 November 2026

| Requirement | Implementation / evidence |
|---|---|
| Request latency and token usage | `app/production.py`, transport-level retries/translation accounting, response metrics and structured logs |
| Simple cache | Conversation-scoped 128-entry / 300-second LRU; anonymous bypass; scope/TTL/invalidation tests |
| Input limits | `app/security.py`, request middleware and Pydantic fields; 413/422 and no-echo tests |
| Prompt-injection test | `tests/test_day13_production.py`: malicious input, poisoned retrieval, output leakage and safe-question cases |
| Production numbers | `eval/production_benchmark.json`, five live Groq repeat pairs; first failed attempt retained |
| Product README | Problem, Mermaid architecture, demo video and measured results |
| Resume | `docs/resume.md`, three factual bullets |
| Extra reliability work | Scope isolation, unknown-usage accounting, bounded eviction, strict provider schema, privacy-conscious logs and CI benchmark artifact |

Full offline suite: **120 passed in 63.97 seconds**. A prior 117-test run also passed;
the final suite includes strict schema, identifier limit and UI confirmation checks.
Ruff lint and format checks pass (47 Python files formatted). Docker Compose
configuration validation passes using `.env.example`. The synthetic CI benchmark
also passes all five repeat pairs and the conversation isolation check.

GitHub/Render status: Day 13 release completed and verified live on Render on 21 November 2026.
- Pull request: [PR #2](https://github.com/omkadam78/GenAI-Traning-Program/pull/2)
- Feature commit: `c4f168d`
- PR CI run: [CI Run #44866833713](https://github.com/omkadam78/GenAI-Traning-Program/actions/runs/44866833713) (passed: Ruff, pytest, Docker build and smoke)
- Merge commit: `92bc6c8`
- Main branch CI run: [CI Run #44867204315](https://github.com/omkadam78/GenAI-Traning-Program/actions/runs/44867204315) (passed: Ruff, pytest, Docker build and smoke)
- Live Render deployment: auto-deployed on check passage to https://fasalbima-sathi.onrender.com
- Live verification results:
  - Public health (`/health`): 200 OK with `ProductionMiddleware` metrics headers (`x-cache`, `x-request-id`, `x-llm-calls`, `server-timing`)
  - Streamlit UI and WebSocket connection: 101 Switching Protocols verified via RFC6455 handshake
  - Input limits: >2,000 char question returned 422, >16 KiB body returned 413
  - Personal claim-status refusal: Q6 returned standard out-of-scope refusal
  - Bounded caching & Groq synthesis: First request MISS (1 LLM call, 3 citations, 1,956 tokens); repeated request with distinct request ID in same thread was HIT (0 LLM calls, 0 tokens); separate thread was MISS (scope isolation verified)
  - Financial calculation & human-in-the-loop approval: Soybean Kharif 2 ha calculation paused at approval gate; resumed on approval with Python tool execution (Sum Insured ₹58,800.00, Farmer Share ₹1,176.00)
The training tracker was NOT updated: write permission was denied. No star or reviewer rating is claimed.
