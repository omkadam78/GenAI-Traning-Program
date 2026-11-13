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

## Current Progress (Days 1–6)
- **Day 1**: Python intro (`day01_intro.py`) and interactive menu (`day01_menu.py`).
- **Day 2**: 20 starter PMFBY records (`data/sample_records.py`), reusable record utilities (`app/records.py`), and terminal CLI (`app/cli.py`).
- **Day 3**: Official source downloader with manifest (`app/fetch.py`), `Record` dataclass (`app/models.py`), and PDF/HTML ingestion pipeline (`app/ingest.py` -> `data/records.json`).
- **Day 4**: FastAPI service (`app/main.py`), TF-IDF + cosine similarity search (`app/smart_search.py`), and pandas dataset analysis (`analysis/explore.py`).
- **Day 5**: LLM fundamentals guide with diagram (`docs/how_llms_work.md`) and 10 evaluation questions (`eval/questions.json`, `docs/questions.md`).
- **Day 6**: LLM provider wrapper supporting Groq & Gemini with offline rule fallback (`app/llm.py`), prompt engineering templates (`prompts/system_prompt.txt`, `prompts/task_v1_concise.txt`, `prompts/task_v2_detailed.txt`), `POST /chat` returning structured JSON (`answer`, `confidence`, `follow_up`), configuration template (`.env.example`), and evaluation report comparing both prompt versions (`eval/prompt_compare.md`).

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

### 4. Explore dataset with pandas (Day 4)
```powershell
python -m analysis.explore
```

### 5. Start the FastAPI server (Days 4–6)
```powershell
uvicorn app.main:app --reload
```
Open Swagger UI docs at `http://127.0.0.1:8000/docs`.

Available endpoints:
- `GET /health`
- `GET /records?limit=5`
- `GET /records/{id}`
- `GET /search?q=hailstorm`
- `POST /questions` (Day 4 TF-IDF rule lookup)
- `POST /chat` (Day 6 LLM endpoint with `message`, `prompt_version`, returning `answer`, `confidence`, `follow_up`)

Example `/chat` request:
```json
{
  "message": "What premium do I pay for soybean crop insurance in kharif?",
  "prompt_version": "v2"
}
```

### 6. Run tests
```powershell
python -m pytest -v
python tests/test_records.py
```

## Disclaimer
Information from official PMFBY guidelines, not insurance or legal advice. Claim decisions rest with the insurance company and the state government.
