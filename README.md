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
- **Sum Insured**: $\text{Scale of Finance} \times \text{Insured Area (ha)}$
- **Farmer Premium Rate**:
  - Kharif food grains & oilseeds (e.g. Soybean): **2.0%**
  - Rabi food grains & oilseeds (e.g. Wheat): **1.5%**
  - Annual commercial & horticultural crops (e.g. Cotton): **5.0%**
- **Farmer Premium Share**: $\text{Sum Insured} \times \text{Rate \%}$

### 2. Hand-Written Agent Loop (`app/agent_loop.py`)
A pure Python ReAct loop that coordinates multi-step inquiries, tool calling, and observation tracking without third-party frameworks. Automatically combines premium calculations with localized calamity intimation guidance for compound queries (e.g., Question 4).

### 3. Stateful LangGraph with Memory & Approval Step (`app/graph.py`)
Rebuilds the agent inside a stateful `StateGraph`:
- **Memory**: Persistent checkpointer (`MemorySaver`) preserving context across turns via `thread_id`.
- **Human-in-the-Loop Approval**: Financial calculations and formal premium estimations require explicit user confirmation before execution (`requires_approval = True`, `status = "approval_required"`). Upon sending `approved = True` on the same `thread_id`, the agent resumes from memory and finalizes the calculation.
- **Strict Safeguard**: Intercepts unanswerable personal claim status questions (Q6 & Q15) with `"I don't know"`.

## RAG Evaluation: 2 Configurations Comparison (Day 8)

Evaluated on 15 test questions from `eval/eval_set.json` (13 answerable guideline scenarios + 2 mandatory refusal queries Q6 and Q15):

| Configuration | Chunk Size | Top-K | Retrieval Recall | Refusal Accuracy (Q6 & Q15) | Overall Accuracy | Avg Latency | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Config A (Compact / top-3)** | 400 chars | 3 | 69.2% | 100.0% | 73.3% | 857.4 ms | Alternative |
| **Config B (Broader Context / top-5)** | 750 chars | 5 | 92.3% | 100.0% | 93.3% | 719.9 ms | **WINNER** |

**Winner Analysis**: **Config B (Broader Context / top-5)** provides optimal chunk cohesion, capturing entire PMFBY policy provisions without splitting clauses while maintaining rapid retrieval and 100% precision on unanswerable status refusals.

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

Example 1: LangGraph Agent with Approval Step (`POST /agent`):
```json
// Turn 1: Request calculation
POST /agent
{
  "query": "Calculate premium for 1.2 ha soybean at scale of finance Rs 49,000 per ha",
  "thread_id": "session_101",
  "agent_type": "langgraph"
}
// Response: {"status": "approval_required", "requires_approval": true, "answer": "Approval Required: Please confirm calculation..."}

// Turn 2: User confirms approval
POST /agent
{
  "thread_id": "session_101",
  "approved": true,
  "agent_type": "langgraph"
}
// Response: {"status": "completed", "requires_approval": false, "answer": "PMFBY Premium Calculation (Confirmed): Sum Insured: ₹58,800.00, Farmer Premium Share: ₹1,176.00..."}
```

Example 2: Hand-written Agent Loop (`POST /agent`):
```json
POST /agent
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
