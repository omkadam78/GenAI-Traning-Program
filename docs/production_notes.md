# Production notes — Day 13

Measured on 21 November 2026. Day 13 was merged via PR #2 and its main CI passed;
the public deployment was verified on 21 November. See `docs/day13_verification.md`
for that historical evidence and `docs/day14_verification.md` for fresh release
checks. These local benchmark measurements are not Render network latency or an
accuracy score. A past successful deployment is not a guarantee of current uptime.

## Reproducible measurements

`python -m eval.production_benchmark --mock --output test-results/cache-benchmark.json`
runs a deterministic regression benchmark without secrets; CI retains its artifact.
For a real measurement, configure Groq privately and run:

```powershell
python -m eval.production_benchmark --live --env-file .env --output test-results/demo-day-live-benchmark.json
```

Keep provider credentials in ignored `.env`; the command does not print them.
The new output path preserves the retained original report. The retained report
uses local FastAPI TestClient, real retrieval and Groq
`openai/gpt-oss-20b`. Five public PMFBY questions each have an initial request and
an exact repeat in the same conversation, with distinct request IDs. This tests
answer caching, not idempotency replay. A separate conversation must miss.
Live cases are paced 35 seconds apart. First retrieval can include cold model/index
loading. Small sample, one machine, one run: results are descriptive, not an SLA.

| Measurement | Observed |
|---|---:|
| Passing repeat pairs | 5 / 5 |
| Median initial request | 1,747.70 ms |
| Median cached request | 376.53 ms |
| Reduction between those medians | 78.46% |
| Initial calls' reported tokens across five pairs | 12,184 |
| Repeated calls' provider requests / tokens | 0 / 0 |
| Different-conversation cache isolation | Passed |
| Offline pytest suite | 120 passed in 63.97 s |

Source: [complete live report](../eval/production_benchmark.json). Answers matched
within all five pairs and retained citations. This does not establish factual
accuracy, savings in rupees, farmer adoption or improved claim outcomes.

The [first attempt](../eval/production_benchmark_first_attempt.json) is also retained:
only 2/5 pairs passed; provider errors and rate limiting occurred. The final run
uses pacing and supported strict structured output with low reasoning effort for
the configured GPT-OSS model. The exact original HTTP 400 cause was not established.
Retries cannot eliminate quota limits. Gemini fallback has not been live-tested.

## Cache boundaries

The in-process, thread-safe LRU stores at most 128 successful live answers for
300 seconds. Anonymous requests bypass caching. Keys include a hash of conversation
scope, exact question, selected evidence, prompts, language, provider/model settings
and credential fingerprints. Different evidence or configuration invalidates a hit.
Calculations, approvals, deadline clocks, failures and deterministic offline responses
are not cached. Restart clears the cache. Multiple workers do not share it and
concurrent misses can each call the provider; there is no distributed single-flight.
Conversation IDs scope data but do not authenticate users: use unpredictable IDs,
and add authentication and owner binding before handling personal information.

## Accounting and privacy

Structured per-request logs record generated request ID, route template, HTTP status,
processing latency, physical provider attempts, failures, cache status and token usage.
Retries, fallback and translation attempts are included. Unknown provider usage is
`null`, not an invented zero; `known_total_tokens` retains the observable subtotal.
A cache hit records zero new provider calls/tokens and separately retains original
answer usage. These are provider-reported tokens, not a billing reconciliation.
End-to-end fallback latency includes the failed primary attempt.

Metrics logs omit raw questions, evidence, conversation IDs, bodies, credentials and
query strings. Uvicorn access logs are disabled in supplied launchers/Compose to
avoid query-string exposure. Platform/proxy logs have separate retention policies.
Cached answer content is held in process memory; never submit private identifiers.

## Input and prompt-injection controls

Question/message/query: 2,000 characters. Request body: 16 KiB. Conversation,
calculation and idempotency identifiers: 128 characters. Feedback comment: 1,000.
Oversized bodies return 413; invalid questions return 422 without echoing input.
The guard normalizes Unicode for inspection, catches tested instruction overrides,
secret requests and approval bypasses, and filters poisoned evidence before citation
selection. Context is escaped JSON; model outputs are checked for credential leakage.
Arithmetic and explicit calculation confirmation stay in Python, outside the LLM.

Tests cover 13 malicious-question variants (including Marathi/Hindi and obfuscation),
poisoned evidence, output leakage, legitimate questions, TTL/LRU, scope separation,
retry accounting and translation usage. Pattern guards are defense in depth; encoded,
novel or paraphrased attacks can evade them. No claim of universal injection safety.
Request size limits are not rate limiting or abuse prevention. Free Render storage,
conversation memory and cache reset on restart; feedback remains ephemeral.
