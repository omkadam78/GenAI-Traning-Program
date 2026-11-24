# FasalBima Sathi — interview and viva guide

Owner: Om Kiran Kadam · 2124UDSM2013. Prepared 22 November 2026.

## Technical defense and reading routes

For code-level follow-ups, read [Engineering defense](engineering_defense.md):
request sequence, approval failure matrix, cache versus idempotency, design
alternatives, stored evaluation error analysis, threat model and offline commands.
It supplements the ten answers below with evidence rather than adding unverified
features. Personal practice status is in [Presentation preparation](presentation_preparation.md).

## My 60-second pitch

FasalBima Sathi helps farmers understand crop insurance without having to read long
PMFBY documents. A farmer can ask in English, Marathi or Hindi, review a premium
estimate, or prepare to report crop loss. I built it with Python, FastAPI,
Streamlit, Chroma and LangGraph. Knowledge answers use retrieved official passages
with source references, while Python calculates premiums and reporting deadlines.
Calculations pause for the user's confirmation. The app cannot access a farmer's
personal claim status, so it refuses that request honestly. I added request metrics,
input limits, injection tests and a conversation-scoped cache. Across five local
live-Groq repeat-question pairs, median latency fell from 1.75 to 0.38 seconds,
with no new provider calls on cache hits. The project has 120 automated tests and
Docker smoke checks in CI. It is live on Render; real farmer adoption and claim
outcomes have not yet been measured.

About 140 words; speak naturally and time it. Do not claim to have memorized or
rehearsed it until you actually have. The latency result is local, not Render latency.

## Ten likely questions and answers

### 1. What problem does it solve, and for whom?

It makes official PMFBY rules easier to navigate for farmers and support workers.
The three main jobs are understanding a rule, estimating the farmer premium and
preparing timely loss reporting. It provides independent guidance; it does not
sell cover, file a claim or decide eligibility. Existing official apps offer actual
enrolment and tracking, so I position this as an explanation/preparation companion.

### 2. Explain one request from screen to answer.

The UI sends a question, language and conversation ID to FastAPI `/agent`.
Middleware checks the input and starts request metrics. LangGraph selects the
knowledge or tool route. Knowledge search retrieves official records/passages;
suspicious evidence is removed before prompt construction. A valid answer-cache
hit avoids synthesis; otherwise the provider generates a structured answer from
that context. The UI shows the answer and citations. Python handles arithmetic.
See `app/main.py`, `app/graph.py`, `app/tools.py`, `app/llm.py` and `app/production.py`.

### 3. Why RAG instead of only prompting or fine-tuning?

RAG supplies document evidence at request time and keeps source/page metadata.
It lets me update the corpus without retraining a model. It does not guarantee
correctness: wrong retrieval, old rules or a weak synthesis can still produce a
bad answer. Fine-tuning would not itself make a rule current or provide citations.
This project does not fine-tune a model; it embeds documents and retrieves chunks.

### 4. What are embeddings, Chroma and top-k doing?

MiniLM maps passages and questions into vectors so semantic similarity can retrieve
related text. Chroma persists the vectors and metadata. Top-k controls how many
matches reach the answer step: too few may omit needed evidence; too many may add
noise and token cost. The isolated 400-character/top-3 and 750-character/top-5
evaluation separates retrieval evidence from answer keywords and refusal behavior.
The current table is heuristic evaluation, not a human-validated accuracy study.

### 5. Why LangGraph, memory and an approval step?

Graph state makes routing, conversation memory and pause/resume explicit. Native
`interrupt()` pauses the calculation, and `Command(resume=...)` continues it after
the user decides. The approval is bound to the pending calculation ID and parameters.
A mismatched ID or replay is rejected. Memory is isolated by thread, but a thread
ID is not authentication. Checkpoints are in process and disappear on restart.

### 6. How do you keep financial calculations accurate?

The LLM does not multiply the premium. A validated Python tool uses the selected
crop/season rule, area unit and scale-of-finance unit. With 1.2 hectares and ₹49,000
per hectare, sum insured is ₹58,800; at the 2% ceiling the estimated maximum farmer
share is ₹1,176. Actual rates can be lower. Tests include invalid values, unit
conversion and lower actuarial rates. A correct formula still needs the applicable
state/season notification and inputs; this is not a binding insurance quotation.

### 7. How does your cache work without mixing conversations?

It is an in-process, thread-safe LRU of at most 128 entries with 300-second expiry.
Only successful live synthesis is cached. Its hashed key includes conversation
scope, question, evidence, prompts, language and provider/model/credential settings.
Anonymous calls bypass it. Different conversations must miss. Calculations,
approvals, errors and live deadline clocks are not cached. It is not distributed,
and simultaneous misses can both call the provider.

### 8. How do you measure speed, tokens and correctness?

I separate three things. The RAG evaluation reports heuristic evidence/answer,
refusal and citation checks. The five-pair live-provider benchmark measures local
request latency and actual reported token usage, with distinct request IDs so hits
cannot be idempotency replays. Transport accounting includes retries, fallback and
translation; unknown usage stays null. Finally, tests and real container smoke
checks validate behavior and startup. None of those prove farmer impact or perfect
factual accuracy. The failed first benchmark remains in the repository.

### 9. How do you address prompt injection and privacy?

Input/body limits bound requests. The guard normalizes text for inspection and
catches tested instruction overrides, filters suspicious evidence, escapes context
JSON and checks model output for credential leakage. Q6 must refuse personal status.
Request metrics omit questions and credentials. Pattern guards can be bypassed by
novel attacks; this is defense in depth. Public deployment still needs stronger
abuse controls, retention policies and authenticated ownership before personal data.

### 10. How is it deployed, and what would you improve next?

Docker packages the API, UI and gateway on one public port. GitHub Actions runs
Ruff, offline pytest and real container/Compose smoke checks before Render deploys.
The smoke checks include health, UI, a WebSocket handshake and Q6 refusal.
Free hosting can sleep; feedback and conversation state are ephemeral. Next I would
validate current source versions/seasonal notifications, test usability with farmers,
and add appropriate persistence, monitoring and abuse protection. The separate
Android prototype is outside the training release and is not a published app.

## My hardest-problem story: current rules, correct units and honest evidence

**Situation:** A crop-insurance answer can look convincing while using the wrong
season, units or source. Retrieval alone cannot establish which notification applies.

**Task:** Make calculations explainable and stop evaluation from confusing keyword
presence in retrieved text with a correct synthesized answer.

**Action:** I kept arithmetic in validated Python, preserved source metadata, added
confirmation and ID binding, and separated evidence support, answer-keyword checks,
refusals and citation completeness in evaluation. I documented the older optimistic
93.3% keyword score rather than treating it as proven accuracy.

**Result:** The calculation/unit/refusal regressions are automated. The historical
comparison is explained in README and `eval/rag_compare.json`. Source freshness and
state/season applicability remain real-world release limitations, not solved claims.

## One failure I fixed: deployment startup readiness

The first Day 12 container CI failed while the application was starting. I added
bounded handling for connection resets/socket errors in `deploy/smoke.py` and
`deploy/serve.py`, rather than bypassing the smoke step. Subsequent PR/main CI
built and started the real image successfully. Evidence: commit `56231d5`, merged
PR #1, and the linked successful CI runs in README. Explain readiness vs liveness:
a process existing does not prove its UI, API and WebSocket are ready.

## One experiment that initially failed

The first live cache benchmark passed only 2/5 pairs with provider failures/rate
limits. I retained it, paced the final cases and used supported structured output.
The final run passed 5/5. I did not establish the exact original HTTP 400 cause, so
I must not say that a specific fix conclusively caused the improvement. The measured
78.46% reduction compares medians in a five-pair local sample, not a production SLA.

## Rapid follow-ups

- **Can I check my personal claim?** No authorized insurer integration exists here.
- **Is Marathi perfect?** No; translation may lose meaning. Native-speaker testing remains.
- **Are citations proof?** They identify evidence; they do not independently verify every claim.
- **Are 120 tests enough?** They cover specified behavior, not every input or real-device scenario.
- **Why no guaranteed star/claim outcome?** Reviewers and insurers make those decisions.
- **Who wrote the code?** Explain your real use of coding assistants honestly. Demonstrate
  the code and decisions you understand; do not imply unaided authorship.

## Preparation record

Read this aloud, run the two demo rounds in `docs/demo_runbook.md`, and record the
actual times and corrections in `docs/presentation_preparation.md`. Interview readiness requires your
explanation and practice; a generated document cannot substitute for that.
