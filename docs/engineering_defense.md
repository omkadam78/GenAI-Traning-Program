# FasalBima Sathi: engineering decisions and reproducible defense

Owner: Om Kiran Kadam · 2124UDSM2013. Added 24 November 2026.

This is a Day 14 technical defense of implemented behavior, not a claim of new
production features or personal rehearsal. Run the linked tests to challenge it.

## 1. Trace one financial request, including the unhappy paths

Example: soybean, Kharif, 1.2 hectares, finance ₹49,000 per hectare.

```mermaid
sequenceDiagram
    actor Farmer
    participant UI as Streamlit
    participant API as FastAPI
    participant Graph as LangGraph
    participant Tool as Python premium tool
    Farmer->>UI: Request estimate
    UI->>API: POST /agent with thread and request IDs
    API->>Graph: Validated request
    Graph-->>UI: Pending calculation ID and interpreted inputs
    Farmer->>UI: Confirm those inputs
    UI->>API: Approval with matching calculation ID
    API->>Graph: Resume pending interrupt
    Graph->>Tool: Validated parameters
    Tool-->>UI: ₹58,800 sum insured; ₹1,176 estimated maximum share
```

Read `app/main.py`, then `classify_node`, `approval_gate_node` and
`run_langgraph_agent` in `app/graph.py`, then `pmfby_premium` in `app/tools.py`.

| Boundary | Required behavior | Concrete regression |
|---|---|---|
| Missing area or finance | Ask rather than invent an input | `test_handwritten_agent_behavior` |
| Invalid numeric/unit input | Reject before producing an amount | `test_pmfby_premium_input_validation` |
| Acres instead of hectares | Convert supported units explicitly | `test_acres_to_hectares_conversion` |
| Wrong approval ID | Reject; preserve the legitimate pending interrupt | `test_approval_requires_exact_calculation_id_and_preserves_interrupt` |
| Second calculation | Require fresh approval | `test_two_successive_calculations_require_fresh_approval` |
| Separate conversation | Do not inherit another conversation's state | `test_conversation_isolation` |

The arithmetic is 1.2 × 49,000 = 58,800; 58,800 × 0.02 = 1,176 for this
illustrated rule. Correct arithmetic is not proof that a historical rule applies
to a specific farmer today. A current notification and correct inputs still matter.

**Alternative considered:** let the LLM return the final number directly.
**Decision:** use Python validation and calculation, then render the result.
**Trade-off:** explicit tools require domain rules and unit handling, but arithmetic
and rejection behavior can be tested independently of generated prose.

## 2. Two safeguards that look similar but solve different problems

| | Idempotency | Answer cache |
|---|---|---|
| Question answered | Have we already processed this request? | Can this successful synthesis be reused? |
| Identity | Request identifier plus payload consistency | Scoped question, evidence, prompt and configuration |
| Repeated identifier, changed payload | Conflict rather than reuse | Not the cache's responsibility |
| Different conversations | Not an ownership/authentication mechanism | Different scopes must miss |
| Financial approval | Protect request handling | Not an ordinary cached knowledge answer |
| Proof | API reliability tests | Cache transport/isolation tests and benchmark |

The five-pair benchmark uses distinct request IDs for initial and repeated calls.
Otherwise an idempotent replay could falsely appear to prove answer-cache savings.
Both mechanisms are in-process; neither is a distributed transaction system.

## 3. Why the cache key includes evidence and configuration

Read `answer_cache_key` and `AnswerCache` in `app/production.py`.

Same question is insufficient: different source passages, prompts, selected
language or model settings may require a new answer. Conversation scope prevents
ordinary cross-thread reuse. Credential fingerprints support invalidation without
putting raw credentials in the key. Anonymous synthesis bypasses shared caching.

The cache is a bounded 128-entry LRU with 300-second expiry and copied values.
Tests challenge expiry, eviction, mutation isolation and configuration changes.
The expiry limits reuse; it does not verify that the source itself is current.
Concurrent misses may still call the provider twice. A multi-instance service
would need a shared store and carefully designed request coalescing.

**Rejected shortcut:** global question-only caching. It is simpler but omits
conversation and evidence boundaries. A larger cache is not automatically better.

## 4. Grounding: a citation is necessary evidence, not a truth certificate

Read `app/rag.py`, `app/llm.py`, `app/security.py` and `eval/run_eval.py`.
The `/ask` pipeline and graph knowledge tool are related entry points; the UI's
`/agent` route does not simply forward every request to `/ask`.

| Failure | Why plausible-looking output can be wrong | Existing response / remaining gap |
|---|---|---|
| Wrong passage retrieved | Similar words do not guarantee applicability | Evidence filtering and evaluation; domain review still needed |
| Old guideline retrieved | A real official PDF can be historical | Preserve version metadata; current notifications remain future work |
| Correct passage, wrong explanation | Generation can misread evidence | Grounded prompt and checks; human factual review still needed |
| Personal claim question | General rules contain no individual account state | Explicit refusal, tested without inventing a status |
| Poisoned passage | Source text can contain instructions | Remove suspicious evidence and its citation; pattern defense is incomplete |

### A measured evaluation lesson

The current stored `eval/rag_compare.json` separates retrieval evidence from
generated-answer keyword checks:

| Stored metric | A: 400 chars / top-3 | B: 750 chars / top-5 |
|---|---:|---:|
| Evidence support | 69.2% | 84.6% |
| Heuristic answer accuracy | 53.8% | 69.2% |
| Refusal on the two designated questions | 100% | 100% |
| Citation metadata completeness | 100% | 100% |
| Overall heuristic score | 60.0% | 73.3% |

Config B is better on this small stored evaluation, not proven best for all
questions. Evidence support is measured over 13 answerable cases; refusals use
two cases. The 73.3% overall score corresponds to 11/15 heuristic successes.
Citation completeness checks metadata, not whether every assertion is entailed.

Specific counterexample: Config B Q1 has evidence support but fails the answer
heuristic. Improving retrieval alone therefore does not guarantee a good answer.
Q4 and Q7 fail both checks; investigate retrieval/source coverage before blaming
only synthesis. These are diagnoses from stored output, not newly rerun experiments.

The older 93.3% figure is historical and should not be presented as a validated
current factual accuracy. This correction is an engineering lesson, not a score
to hide. Larger, independently annotated evaluation is a next step.

## 5. Defend a performance result without overstating it

Stored live benchmark: `eval/production_benchmark.json`; retained failed trial:
`eval/production_benchmark_first_attempt.json`.

The five local live-Groq repeat pairs report medians 1,747.70 and 376.53 ms.
The reduction is (1747.70 − 376.53) / 1747.70 × 100 ≈ 78.46%.
This is a reduction between medians, not necessarily the median per-pair reduction.
Initial requests reported 12,184 tokens; repeats made no new synthesis transport
calls. Translation and retries must be included when they occur. Unknown usage
stays unknown, rather than being reported as zero.

The failed trial passed only 2/5 pairs. Pacing and supported structured output
were used for the final trial; the precise original HTTP 400 cause was not proven.
Do not attribute every improvement to a single unisolated change.

The sample is small, local and repeated-question specific. It does not establish
Render latency, cold-start behavior, population-level confidence or farmer impact.

## 6. Threat model and deployment trade-offs

| Asset / failure | Implemented protection | Remaining limitation |
|---|---|---|
| Provider secrets | Server configuration, output checks, safe metrics | Novel leakage paths require further review |
| Expensive requests | Input/body bounds and bounded retries | No complete public abuse/rate-limit control |
| Approval state | Bound calculation IDs and pause/resume tests | Thread IDs are not authenticated ownership |
| Prompt manipulation | Input/evidence/output checks | Novel attacks may bypass patterns |
| Startup reliability | Actual HTTP/UI/WebSocket container smoke | A green build is not continuous availability |
| Feedback and memory | Scope controls and disclosed storage behavior | Ephemeral free-host/in-process state |

**Why single-container deployment?** One public port simplifies this free-host
prototype. API, UI and gateway are supervised together. The compromise is shared
resources and coupled lifecycle. Separate services would allow independent scaling
but add routing, operational and hosting complexity.

**Readiness versus liveness:** a process can exist before dependencies and routes
are ready. Day 12 socket/reset handling was bounded rather than deleting the smoke
check. See commit `56231d5` and the verified PR/main CI links in README.

## 7. Reproduce the defense offline

From the repository root, in the configured environment:

```powershell
python -m pytest -q tests/test_day9_regression.py tests/test_reviewer_fixes.py tests/test_day13_production.py
python -m eval.production_benchmark --mock --output test-results/defense-cache.json
python -m pytest -q --junitxml=test-results/pytest.xml
python -m ruff check .
python -m ruff format --check .
```

Mock mode tests behavior without provider credentials. It cannot measure live
provider quality or latency. Fresh follow-up results are in
`docs/day14_followup_verification.md`. Original historical evidence remains intact.

## 8. Explain these decisions without reading a script

1. Trace one premium request and deliberately cancel it before trying approval.
2. Explain why correct arithmetic can still give inapplicable insurance guidance.
3. Explain why a retry, cache hit and idempotent replay are different.
4. Use Q1 versus Q4 from stored evaluation to separate retrieval and synthesis errors.
5. Describe one limitation you would prioritize before serving personal data.

These are personal practice prompts, not completed rehearsal claims. Presentation
timing and Day 15 participation remain in `docs/presentation_preparation.md`.
