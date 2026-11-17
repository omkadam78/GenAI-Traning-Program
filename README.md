# FasalBima Sathi

An AI-powered assistant for the Pradhan Mantri Fasal Bima Yojana (PMFBY).

## Problem
Farmers often face difficulty understanding crop insurance guidelines, premium calculations, claim procedures, and deadlines (such as the 72-hour localized calamity intimation window).

## Target Users
- Indian farmers (e.g., soybean farmers facing localized hailstorm losses)
- Small and marginal farmers
- Agricultural support organizations

## Project Objectives
- Explain PMFBY rules in simple language.
- Help farmers understand crop insurance procedures, premium caps, and exclusions.
- Provide reliable information with references to official guideline versions and URLs.
- Support farmers in understanding claim-related deadlines.

## Official Data Sources
- https://pmfby.gov.in/faq
- https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf
- https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf

## Current Progress (Days 1–9)
- **Day 1**: Python intro (`day01_intro.py`) and interactive menu (`day01_menu.py`).
- **Day 2**: 20 starter PMFBY records (`data/sample_records.py`), reusable record utilities (`app/records.py`), and terminal CLI (`app/cli.py`).
- **Day 3**: Official source downloader with manifest (`app/fetch.py`), `Record` dataclass (`app/models.py`), and PDF/HTML ingestion pipeline (`app/ingest.py` -> `data/records.json`).
- **Day 4**: FastAPI service (`app/main.py`), TF-IDF + cosine similarity search (`app/smart_search.py`), and pandas dataset analysis (`analysis/explore.py`).
- **Day 5**: LLM fundamentals guide with diagram (`docs/how_llms_work.md`) and 10 evaluation questions (`eval/questions.json`, `docs/questions.md`).
- **Day 6**: LLM provider wrapper supporting Groq & Gemini with offline rule fallback (`app/llm.py`), prompt engineering templates (`prompts/system_prompt.txt`, `prompts/task_v1_concise.txt`, `prompts/task_v2_detailed.txt`), `POST /chat` returning structured JSON (`answer`, `confidence`, `follow_up`), configuration template (`.env.example`), and evaluation report comparing both prompt versions (`eval/prompt_compare.md`).
- **Day 7**: Document chunking pipeline preserving source, page, and title (`app/chunking.py`), dense semantic embedding utilities (`app/embed.py`), persistent Chroma vectorstore (`app/vectorstore.py` with 1,786 indexed chunks), `GET /search/semantic` endpoint, and semantic evaluation report on 10 questions (`eval/search_results.md`).
- **Day 8**: Grounded RAG engine with strict citations and personal claim refusal (`app/rag.py`), `POST /ask` endpoint, 15-question evaluation suite (`eval/eval_set.json`), dual-configuration experiment script (`eval/run_eval.py`), and configuration winner table below.
- **Day 9**: Agent tools (`app/tools.py` with `pmfby_premium` pure arithmetic calculation, `pmfby_knowledge_search`, and `pmfby_claim_deadline_check`), hand-written ReAct-style agent loop (`app/agent_loop.py`), stateful LangGraph agent with conversation memory (`MemorySaver`) and human-in-the-loop approval step (`app/graph.py`), and unified `POST /agent` endpoint.

## Day 9: Agent Tools, Hand-Written Loop & LangGraph

### 1. Pure Arithmetic Premium Tool (`app/tools.py`)
Calculates PMFBY sum insured and farmer premium share using official rates from `data/records.json`:
- **Sum Insured**: $\text{Scale of Finance (₹/ha)} \times \text{Insured Area (ha)}$
- **Area Units**: Explicitly supports hectares (`ha`, `hectare`) and acres (`acre`, `acres` converted at $1 \text{ acre} = 0.404686 \text{ ha}$). Unsupported units (e.g. bigha, guntha) are rejected with clear error messages.
- **Monetary Precision**: Uses Python `Decimal` with documented `ROUND_HALF_UP` quantization to ₹0.01.
- **Input Validation**: Strictly rejects booleans, NaN, infinity, negative or zero amounts, and invalid actuarial rates.
- **Farmer Premium Rate & Ceilings**:
  - Kharif food grains & oilseeds (e.g. Soybean): **2.0%**
  - Rabi food grains & oilseeds (e.g. Wheat): **1.5%**
  - Annual commercial & horticultural crops (e.g. Cotton): **5.0%**
- **Rate Ambiguity Handling**: If crop or season is missing or unverified against `records.json`, the agent halts and requests clarification rather than inventing a rate.
- **Premium Estimation**: Distinguishes between an **estimated maximum farmer premium** (capped at the statutory rate) when tender rates are unnotified, and an **exact premium** when the tender actuarial rate is provided ($\min(\text{statutory\_cap}, \text{actuarial\_rate})$).

### 2. Intimation Deadline Clock (`app/tools.py`)
Computes the 72-hour localized calamity and post-harvest intimation deadline under Revamped PMFBY Guidelines (Para 15.1.2 & 15.2.2):
- **Timezone**: Evaluates in `Asia/Kolkata` (IST).
- **Date Parsing**: Supports ISO timestamps (`YYYY-MM-DD HH:MM`) and relative expressions (`yesterday at 9 pm`, `12 hours ago`).
- **Injectable Clock**: Accepts an injectable clock `now` for deterministic regression testing.
- **Strict Validation**: Rejects invalid or missing timestamps; never silently substitutes the current time. Only reports execution in tool traces when the function actually ran.

### 3. Hand-Written Agent Loop (`app/agent_loop.py`)
A pure Python ReAct loop coordinating multi-step farmer inquiries:
- Dispatches `pmfby_premium`, `pmfby_knowledge_search`, and `pmfby_claim_deadline_check`.
- Truthful tool traces: only reports tools that actually executed.
- Enforces `max_iterations: 5`.
- Strict refusal safeguard: intercepts individual claim approval or payment inquiries (Q6 & Q15) with `"I don't know"` and `0.0` confidence.

### 4. Stateful LangGraph with Memory & Approval Step (`app/graph.py`)
Rebuilds the agent into a stateful `StateGraph`:
- **Session Memory**: Uses LangGraph `MemorySaver`. State is strictly isolated per conversation ID (`thread_id`). If omitted, a unique session ID (`session_<uuid>`) is generated and returned.
- **Human-in-the-Loop Approval Step**:
  - Every NEW calculation resets approval and pauses for user confirmation (`status: "approval_required"`, `requires_approval: true`).
  - Parameters are bound to a unique calculation ID (`calc_<uuid>`).
  - Resuming requires an active pending calculation on the session. Submitting `approved: true` without a pending calculation is rejected (`status: "rejected"`).
  - Cancellation (`approved: false`) cancels the pending request without executing any tools (`status: "cancelled"`).
  - Replay protection: once executed or cancelled, the pending calculation is cleared.
  - Follow-up knowledge questions on the same session execute cleanly without reusing previous calculation parameters.
- **Memory Limitations**: `MemorySaver` maintains multi-turn session state in RAM during application server runtime. In-memory checkpoints do not persist across process restarts; persistent production deployments would require external storage checkpointers such as `SqliteSaver` or `PostgresSaver`.

## RAG Evaluation: 2 Configurations Comparison (Day 8)

The dual-configuration benchmark evaluated 15 test scenarios from `eval/eval_set.json` (13 answerable PMFBY guideline questions + 2 mandatory refusal queries Q6 and Q15):

| Configuration | Chunk Size | Top-K | Keyword Retrieval Recall | Refusal Accuracy (Q6 & Q15) | Historical Benchmark Result | Avg Latency | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Config A (Compact / top-3)** | 400 chars | 3 | 69.2% | 100.0% | 73.3% | 857.4 ms | Alternative |
| **Config B (Broader Context / top-5)** | 750 chars | 5 | 92.3% | 100.0% | 93.3% | 719.9 ms | **WINNER** |

> [!NOTE]
> **Evaluation Methodology & Limitations**:
> The 93.3% score represents a **historical keyword-based retrieval benchmark result** (verifying that retrieved chunks contain expected topic keywords and that unanswerable claim queries are refused). It does not represent verified natural-language factual accuracy across all possible queries. The benchmark queries the pre-indexed Chroma vectorstore.

## How to run

### 1. Setup environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure environment (Optional - LLM API keys)
Copy `.env.example` to `.env` to test with live Groq or Gemini keys:
```powershell
Copy-Item .env.example .env
```
*(Note: Never commit `.env` to Git. If no keys are provided, the system automatically uses the high-precision offline PMFBY rule engine fallback.)*

### 3. Fetch & ingest PMFBY data (Day 3)
```powershell
python -m app.fetch
python -m app.ingest
```

### 4. Index Chroma Vectorstore (Day 7)
```powershell
python -m app.vectorstore
```

### 5. Run RAG Evaluation (Day 8)
```powershell
python -m eval.run_eval
```

### 6. Start the FastAPI server (Days 4–8)
```powershell
uvicorn app.main:app --reload
```
Open Swagger UI docs at `http://127.0.0.1:8000/docs`.

Available endpoints:
- `GET /health`: service health and record count
- `GET /records`: list PMFBY rule records
- `GET /records/{id}`: read single record by ID
- `GET /search?q=hailstorm`: keyword search over rule records
- `GET /search/semantic?q=hailstorm`: semantic vector search over 1,786 Chroma chunks
- `POST /questions`: Day 4 TF-IDF rule lookup
- `POST /chat`: Day 6 prompt-engineered LLM chat (`message`, `prompt_version`)
- `POST /ask`: Day 8 grounded RAG endpoint answering questions from retrieved chunks with citations (strictly refuses private claim queries with `"I don't know"`)
- `POST /agent`: Day 9 agent endpoint supporting both LangGraph (with memory + approval step) and hand-written agent loops

### Working API Examples (`POST /agent`)

#### Example 1: New Session & Approval Lifecycle (LangGraph)
```http
POST /agent
Content-Type: application/json

{
  "query": "Calculate premium for 1.2 ha soybean at scale of finance Rs 49,000 per ha",
  "agent_type": "langgraph"
}
```
**Response (Turn 1 - Session Created & Approval Required):**
```json
{
  "thread_id": "session_8f4a12bc90de",
  "status": "approval_required",
  "requires_approval": true,
  "answer": "**Approval Required for PMFBY Calculation:**\n- Calculation ID: `calc_3e71ab01`\n- Crop: Soybean\n- Area: 1.2 ha\n- Scale of Finance: ₹49,000.00/ha\n\nTo proceed, submit with approved: true on session `session_8f4a12bc90de`."
}
```

**Turn 2A: Confirm Approval:**
```http
POST /agent
Content-Type: application/json

{
  "thread_id": "session_8f4a12bc90de",
  "approved": true,
  "agent_type": "langgraph"
}
```
**Response (Completed):**
```json
{
  "thread_id": "session_8f4a12bc90de",
  "status": "completed",
  "requires_approval": false,
  "answer": "**PMFBY Premium Calculation (Confirmed):**\n- Sum Insured: ₹58,800.00 (₹49,000.00/ha × 1.20 ha)\n- Farmer Premium Rate: 2.00% (Kharif Soybean)\n- Estimated Maximum Farmer Premium Share: ₹1,176.00"
}
```

**Turn 2B (Alternative): Cancel Approval:**
```http
POST /agent
Content-Type: application/json

{
  "thread_id": "session_8f4a12bc90de",
  "approved": false,
  "agent_type": "langgraph"
}
```
**Response (Cancelled):**
```json
{
  "thread_id": "session_8f4a12bc90de",
  "status": "cancelled",
  "requires_approval": false,
  "tool_calls": [],
  "answer": "Calculation cancelled as requested. No tools were executed and no records were submitted."
}
```

#### Example 2: Acres to Hectares Conversion
```http
POST /agent
Content-Type: application/json

{
  "query": "Calculate premium for 2.47105 acres of soybean at scale of finance Rs 50,000 per ha",
  "agent_type": "langgraph"
}
```

#### Example 3: Hand-Written Agent Loop (Compound Calamity & Premium Query)
```http
POST /agent
Content-Type: application/json

{
  "query": "Hailstorm hit my 1.2 ha soybean at 9 pm yesterday. By when must I inform, through which channels, and what premium did I pay if the scale of finance is Rs 49,000 per ha?",
  "agent_type": "handwritten"
}
```

### 7. Run test suite
```powershell
python -m pytest -v
python tests/test_records.py
```

## Disclaimer
Information from official PMFBY guidelines, not insurance or legal advice. Claim decisions rest with the insurance company and the state government.
