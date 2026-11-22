# Day 14 final verification — 22 November 2026

Owner: Om Kiran Kadam · 2124UDSM2013 · FasalBima Sathi.

## Required deliverables

| Requirement | Evidence |
|---|---|
| 60-second pitch and ten interview answers | `docs/interview.md` |
| Hardest-problem / measurable failure story | Retrieval/evaluation honesty, unit validation, startup recovery and retained failed benchmark in the interview guide |
| Structured closeout | Root `PROGRESS.md` distinguishes implementation, publication, personal practice and external review |
| Demo preparation | `docs/demo_runbook.md`: timed five-minute script, two rounds, recovery table and viva prompts |
| Reproducible benchmark command in README | Both synthetic and optional live commands are now in root README; new outputs preserve the original live report |
| Final release tag | Pending authorized Git publication; do not claim the tag exists until pushed and verified |

## Fresh validation

| Check | Observed result |
|---|---|
| Full offline pytest suite | **120 passed in 102.47 seconds**; isolated feedback and temporary test data |
| Ruff lint and formatting | Passed |
| Compose configuration | Passed using `.env.example`; Docker engine is unavailable locally |
| Synthetic cache benchmark | **5/5 pairs**, scope isolation passed, zero provider calls on repeated cached synthesis |
| Automated product demo rounds | **19 real local Streamlit/HTTP transitions**, both rounds passed |
| Fresh public container smoke | Health, UI, actual WebSocket handshake, records API and Q6 refusal all passed |

The live-provider 78.46% result remains the original five-pair measurement from
21 November. Today's synthetic benchmark is explicitly mock mode; do not present
its latency/token values as real Groq performance. The 22 November UI knowledge
step did use Groq: one physical provider call, 2,614 reported tokens, official
source links, and no service error. It was a functional spot-check, not a new
five-pair benchmark or a statistical accuracy evaluation.

## The two automated demo rounds

**Round 1:** reset; review then approve Soybean/Kharif, 1.2 ha and ₹49,000/ha;
verify ₹58,800 sum insured / ₹1,176 estimated maximum premium; select yesterday's
loss time in IST; verify a live clock and downloadable note; verify personal-status
refusal; ask a real knowledge question and verify official source links.

**Round 2:** reset; review a 2 ha estimate; cancel and verify no calculation metric;
review a fresh request and approve; verify ₹98,000 / ₹1,960; submit an instruction
override; verify UI warning, HTTP 422 and zero provider calls; reset successfully;
switch to Marathi and verify translated guidance renders without exceptions.

The throwaway harness initially expected an `error` element for the rejected input;
the app intentionally renders it as a `warning`. The observation was corrected and
verified against HTTP 422 and zero calls; no application code was weakened/changed.
See [actual transition evidence](../eval/day14_demo_checks.json) and
[public smoke result](../eval/day14_public_smoke.json).

These are automated product rehearsals. They do not prove the student's personal
pitch, timing or viva practice. Follow the runbook twice yourself before presenting.

## Release status and limits

The verified base release is `78b4f08` on GitHub, with successful Day 13 CI. Day 14
changes are documentation and retained verification evidence; application behavior
is preserved. Creating `day-14-final` failed because Git could not write its branch
lock under `.git`, even after session filesystem permission was granted. Therefore
Day 14 commit/PR/CI/final-tag publication must be completed through the authorized
Git environment; none of those operations is claimed done here.

Publishing procedure: push a `day-14:` commit on a feature branch, obtain green CI,
merge, verify main CI and create/push the annotated `final` tag at that exact verified
release. Do not move existing checkpoint tags or manufacture rehearsal/reviewer status.

The seven reviewer stars cover accepted Days 1–13; Day 14 review is external.
Tracker editing still requires the sheet owner's access. The app remains independent
guidance, with historical-rule freshness and free-host persistence limits documented
in `docs/production_notes.md` and `PROGRESS.md`. The separate Android experiment is
outside the scope of this release. Day 15's test/live demo/Q&A remains student work.
