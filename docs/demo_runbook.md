# Five-minute live demo and recovery runbook

Presenter: Om Kiran Kadam · FasalBima Sathi. No real farmer identifiers.

## Before presenting

Open the [live app](https://fasalbima-sathi.onrender.com/), official sources,
[video backup](https://drive.google.com/file/d/1SqBRUVHGCP8iX5eNJeH-B5WiEgFAyB5a/view),
README and CI. Wake the free host ahead of time. Start a new conversation. Keep
the API key in ignored `.env` or Render secrets. Never open that file on screen.
Check the language, units and reporting date before each scenario.

## Timed script

| Time | Show | Explain / verify |
|---|---|---|
| 0:00–0:40 | Home and language selector | Farmer problem; independent guidance. English/Marathi/Hindi are available, but translation can be imperfect. |
| 0:40–1:30 | Ask “What are the farmer premium rates under PMFBY?”; expand sources | Grounded synthesis with document/page references. Show the evidence; do not equate a citation with guaranteed accuracy. |
| 1:30–2:30 | Estimate soybean, Kharif, 1.2 hectares, ₹49,000 per hectare | Review then confirm. Python result: sum insured ₹58,800; estimated maximum farmer share ₹1,176. It does not purchase insurance. |
| 2:30–3:20 | Report crop loss; select an actual example time from yesterday | Applicable localized/post-harvest 72-hour deadline, India time, live clock, checklist and download. No claim is submitted. |
| 3:20–3:45 | Ask “Has my PMFBY claim been approved?” | Honest refusal: no access to insurer records. Never enter a real policy/Aadhaar/bank number. |
| 3:45–4:25 | README Production notes and benchmark JSON | Five-pair live sample, 78.46% reduction between medians; zero new provider calls for repeats. Local timings, not Render latency or factual accuracy. |
| 4:25–5:00 | CI and failure story | Tests, real Docker smoke checks and startup recovery fix. State free-host persistence and source-freshness limitations. |

The pre-recorded video is an edited narrated walkthrough, not proof of live latency.

## Two rounds

1. **Normal round:** follow the full script; verify citations, calculation, clock,
   refusal and metrics. Record actual checks and any failures; do not assume success.
2. **Adversarial/recovery round:** reject a calculation, verify it does not execute,
   submit a fresh calculation, then confirm. Try an instruction-override request;
   demonstrate rejection. Describe network failure/retry and cache scope honestly.
   Do not manufacture a provider outage or expose a key for the demonstration.

Automated/browser rounds validate product behavior. Your own pitch and viva practice
remain your responsibility. Do not record a personal rehearsal time unless you timed it.

## Recovery decisions

| Failure | Response |
|---|---|
| Free host asleep or unavailable | Wait for health; explain the hosting limit. Use the already verified local launcher or clearly label the video backup. |
| Groq quota/provider failure | Show the honest service error. Do not relabel offline/templates as live inference. Use deterministic premium/clock flows while the quota recovers. |
| Approval ID lost after restart | Start a new conversation and review a new estimate. Do not auto-approve or reuse an old ID. |
| Missing evidence | Refuse/qualify the answer and open official sources; do not invent a citation. |
| Clock appears expired | Verify the selected date/time and applicability; contact the insurer promptly. This app cannot decide claim eligibility. |

## Commands from project root

```powershell
python run.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python deploy/smoke.py https://fasalbima-sathi.onrender.com --output test-results/public-smoke.json
python -m eval.production_benchmark --mock --output test-results/cache-benchmark.json
```

For a new **live** measurement, use your ignored `.env` containing the Groq key:

```powershell
python -m eval.production_benchmark --live --env-file .env --output test-results/demo-day-live-benchmark.json
```

This can take several minutes with pacing and consumes provider quota. It measures
local TestClient requests. Preserve the original `eval/production_benchmark.json`.

## Three-minute Q&A

Use `docs/interview.md`: architecture, RAG limitations, deterministic arithmetic,
native graph interruption, honest metrics, cache invalidation, injection limitations,
container readiness and one measurable failure/fix. Answer from evidence, not memorized
claims of perfect accuracy or real-world savings.
