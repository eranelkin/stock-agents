# Stock-Agents — Claude Code Project Prompt

## Project overview

You are building **Stock-Agents**, a Python-based multi-agent AI system that processes a list of stock tickers in parallel. Each ticker is processed by a configurable pipeline of AI agents, each powered by its own prompt. The system is designed to be fully dynamic — no hardcoded LLM logic, no hardcoded agent count, no hardcoded prompts. Everything is driven by configuration files and `.env`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| AI service | asyncio (native parallel processing) |
| LLM routing | `litellm` (provider-agnostic) |
| Backend API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database driver | asyncpg |
| Database | PostgreSQL 16 (Docker) |
| Containerization | Docker + Docker Compose |
| Config | python-dotenv + pydantic-settings |
| Output serialization | PyYAML + json (stdlib) |

---

## Project structure

Scaffold exactly this structure. Do not deviate:

```
stock-agents/
├── .env                        # all secrets and config (never commit)
├── .env.example                # committed version with placeholder values
├── Data.json                   # input: list of ticker objects
├── Prompts.json                # agent prompts (dynamic count)
├── docker-compose.yml
├── pyproject.toml              # dependencies + tool config
│
├── ai-service/
│   ├── __init__.py
│   ├── main.py                 # entrypoint: loads config, runs orchestrator
│   ├── orchestrator.py         # reads Data.json, spawns one Pipeline per ticker
│   ├── pipeline.py             # one pipeline per ticker, fans out to N agents
│   ├── agent.py                # single agent: receives prompt + input, calls LLM
│   ├── aggregator.py           # merges all agent outputs into one result per ticker
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── llm_client.py       # litellm wrapper, fully provider-agnostic
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── input.py            # Pydantic model for Data.json items
│   │   └── output.py           # Pydantic model for aggregated result
│   │
│   └── utils/
│       ├── __init__.py
│       ├── prompt_loader.py    # loads and validates Prompts.json
│       ├── output_writer.py    # writes YAML or JSON output files
│       └── logger.py           # structured logging setup
│
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # pydantic-settings config class
│   ├── Dockerfile
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── runs.py         # POST /runs, GET /runs, GET /runs/{id}
│   │       └── results.py      # GET /results/{run_id}
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py          # async engine + session factory
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── migrations/         # Alembic migrations folder
│   │
│   └── schemas/
│       ├── __init__.py
│       ├── run.py              # Pydantic request/response schemas
│       └── result.py
│
└── outputs/                    # generated output files land here (gitignored)
```

---

## Core architecture rules — read carefully

### 1. The orchestrator
- Reads `Data.json` from the project root.
- Splits the list into individual ticker objects.
- For each ticker, creates one `Pipeline` instance.
- Runs **all pipelines concurrently** using `asyncio.gather()`.
- Waits for all pipelines to complete, then collects results.
- Writes one output file per ticker via `output_writer`.

### 2. The pipeline
- Receives one ticker object and the full prompts dict.
- Creates one `Agent` instance per prompt key (dynamic — do not hardcode 4).
- Runs all agents concurrently using `asyncio.gather()`.
- Passes results to `Aggregator` and returns the merged output.
- **Chain mode vs parallel mode**: the pipeline supports both. If `AGENT_MODE=chain` in `.env`, agents run sequentially and each receives the previous agent's output. If `AGENT_MODE=parallel` (default), all agents run simultaneously with only the ticker as input.

### 3. The agent
- Has no business logic of its own.
- Receives: its prompt string, the ticker input dict, and optionally the previous agent's output (for chain mode).
- Constructs the LLM call: prompt → system role, input data → user role.
- Returns parsed JSON. If the LLM returns unparseable output, log a warning and return `{"raw_output": <string>, "parse_error": true}`.
- Never raises — always returns a dict.

### 4. The LLM client
- Uses `litellm.acompletion()` — async, provider-agnostic.
- Reads `LLM_PROVIDER`, `LLM_MODEL`, and the relevant API key from `.env`.
- No model-specific logic anywhere. The model is just a string passed to litellm.
- Retry logic: 3 attempts with exponential backoff on rate-limit or timeout errors.
- All LLM errors are caught, logged, and re-raised as a custom `LLMError`.

### 5. The aggregator
- Takes the list of agent result dicts for a single ticker.
- Merges them into one output dict with structure:
  ```json
  {
    "ticker": "AAPL",
    "agents": {
      "prompt1": { ...agent1 output... },
      "prompt2": { ...agent2 output... }
    },
    "metadata": {
      "pipeline_duration_ms": 1234,
      "agent_count": 4,
      "timestamp": "2026-05-27T10:00:00Z"
    }
  }
  ```

### 6. Output files
- Written to `./outputs/` directory (created if not exists).
- Format controlled by `OUTPUT_FORMAT` in `.env` (`yaml` or `json`).
- Filename: `output_{TICKER}.{format}` e.g. `output_AAPL.yaml`.
- YAML output uses `yaml.dump()` with `allow_unicode=True, sort_keys=False`.

---

## Configuration — `.env` file

Generate this `.env.example` exactly:

```env
# ── LLM ─────────────────────────────────────────────
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# ── Agent behavior ───────────────────────────────────
AGENT_MODE=parallel             # parallel | chain
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3

# ── Concurrency ──────────────────────────────────────
MAX_CONCURRENT_PIPELINES=10
MAX_CONCURRENT_AGENTS=8

# ── Output ───────────────────────────────────────────
OUTPUT_FORMAT=yaml              # yaml | json
OUTPUT_DIR=./outputs

# ── Database ─────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=stock_agents
POSTGRES_USER=sa_user
POSTGRES_PASSWORD=changeme

# ── Backend ──────────────────────────────────────────
BACKEND_PORT=8000
AI_SERVICE_PORT=8001
SECRET_KEY=change-this-in-production
CORS_ORIGINS=http://localhost:3000
```

---

## `Prompts.json` — structure

```json
{
  "prompt1": "You are a financial data collector agent.\n\nYou will receive a JSON object with a single key 'name' containing a stock ticker symbol.\n\nYour task: Retrieve and summarize the key financial metrics for this ticker.\n\nOutput format: Respond ONLY with a valid JSON object. No explanation, no markdown. Use this exact schema:\n{\n  \"ticker\": \"string\",\n  \"price\": number,\n  \"market_cap\": number,\n  \"pe_ratio\": number | null,\n  \"volume_7d_avg\": number\n}\n\nRules:\n- If a value is unknown or unavailable, use null.\n- Never fabricate data. Use your training knowledge only.\n- Do not include any text outside the JSON object.",

  "prompt2": "You are a market sentiment analysis agent.\n\nYou will receive a JSON object with a stock ticker symbol.\n\nYour task: Analyze the current market sentiment for this ticker based on your training knowledge.\n\nOutput format: Respond ONLY with a valid JSON object:\n{\n  \"ticker\": \"string\",\n  \"sentiment\": \"bullish\" | \"bearish\" | \"neutral\",\n  \"sentiment_score\": number,\n  \"key_drivers\": [\"string\"],\n  \"analyst_consensus\": \"buy\" | \"sell\" | \"hold\" | null\n}\n\nRules:\n- sentiment_score must be between -1.0 (most bearish) and 1.0 (most bullish).\n- key_drivers must be a list of 2-4 concise strings.\n- Do not include any text outside the JSON object.",

  "prompt3": "You are a technical analysis agent.\n\nYou will receive a JSON object with a stock ticker symbol.\n\nYour task: Provide a technical analysis summary for this ticker.\n\nOutput format: Respond ONLY with a valid JSON object:\n{\n  \"ticker\": \"string\",\n  \"trend\": \"uptrend\" | \"downtrend\" | \"sideways\",\n  \"rsi_estimate\": number | null,\n  \"macd_signal\": \"bullish\" | \"bearish\" | \"neutral\",\n  \"key_support\": number | null,\n  \"key_resistance\": number | null\n}\n\nRules:\n- rsi_estimate must be between 0 and 100 if provided.\n- Do not include any text outside the JSON object.",

  "prompt4": "You are a final synthesis and recommendation agent.\n\nYou will receive a JSON object with a stock ticker symbol.\n\nYour task: Based on your comprehensive knowledge of this stock, produce a final investment brief.\n\nOutput format: Respond ONLY with a valid JSON object:\n{\n  \"ticker\": \"string\",\n  \"recommendation\": \"strong_buy\" | \"buy\" | \"hold\" | \"sell\" | \"strong_sell\",\n  \"confidence\": number,\n  \"time_horizon\": \"short\" | \"medium\" | \"long\",\n  \"summary\": \"string\",\n  \"risk_factors\": [\"string\"],\n  \"catalysts\": [\"string\"]\n}\n\nRules:\n- confidence must be between 0.0 and 1.0.\n- summary must be 2-3 sentences maximum.\n- risk_factors and catalysts must each have 2-4 items.\n- Do not include any text outside the JSON object."
}
```

---

## `Data.json` — structure

```json
[
  { "name": "AAPL" },
  { "name": "GOOGL" },
  { "name": "MSFT" },
  { "name": "AMZN" }
]
```

---

## Code quality standards — non-negotiable

- **Type hints everywhere.** Every function signature must be fully annotated. Use `from __future__ import annotations` at the top of every file.
- **Pydantic for all data boundaries.** Any data entering or leaving a component (file reads, LLM responses, API request/response) must be validated by a Pydantic v2 model.
- **Async all the way down.** Every I/O operation must be async. No `time.sleep()`, no blocking file reads in hot paths. Use `aiofiles` for file I/O.
- **Structured logging.** Use Python's `logging` module configured as JSON in production. Every log entry must include `ticker`, `agent_id`, and `pipeline_id` where applicable. No bare `print()` statements.
- **Never swallow exceptions silently.** Catch, log with full traceback, then either re-raise or return a structured error dict.
- **Semaphore-based concurrency limiting.** Use `asyncio.Semaphore` to enforce `MAX_CONCURRENT_PIPELINES` and `MAX_CONCURRENT_AGENTS` from `.env`. Never let unlimited concurrent LLM calls through.
- **No hardcoded values anywhere.** Every configurable value (model name, timeout, output format, file paths) must come from `.env` via the config class.
- **Docstrings on every class and public method.** One-line summary + Args + Returns where non-obvious.

---

## `pyproject.toml` dependencies

```toml
[project]
name = "stock-agents"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "litellm>=1.40.0",
    "aiofiles>=23.2.1",
    "PyYAML>=6.0.1",
    "python-dotenv>=1.0.1",
    "tenacity>=8.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

---

## Docker Compose

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./outputs:/app/outputs

  ai-service:
    build:
      context: .
      dockerfile: ai-service/Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    ports:
      - "${AI_SERVICE_PORT:-8001}:8001"
    volumes:
      - ./outputs:/app/outputs
      - ./Data.json:/app/Data.json:ro
      - ./Prompts.json:/app/Prompts.json:ro

volumes:
  pgdata:
```

---

## Build order

When scaffolding the project, build in this exact order:

1. `pyproject.toml`, `.env.example`, `Data.json`, `Prompts.json`, `docker-compose.yml`
2. `ai-service/utils/logger.py` — logging must exist before anything else
3. `ai-service/schemas/input.py` and `ai-service/schemas/output.py`
4. `ai-service/utils/prompt_loader.py` and `ai-service/utils/output_writer.py`
5. `ai-service/models/llm_client.py`
6. `ai-service/agent.py`
7. `ai-service/aggregator.py`
8. `ai-service/pipeline.py`
9. `ai-service/orchestrator.py`
10. `ai-service/main.py`
11. `backend/db/session.py` and `backend/db/models.py`
12. `backend/schemas/`, `backend/api/routes/`
13. `backend/main.py`
14. `backend/Dockerfile`, `ai-service/Dockerfile`

---

## What NOT to do

- Do not use `requests` — use `httpx` (async) or `litellm` directly.
- Do not use `threading` — this system is entirely async.
- Do not hardcode `4` as the agent count anywhere. Read it from `len(prompts)`.
- Do not hardcode any model name, provider, or API key in code.
- Do not use `print()` for logging.
- Do not catch bare `Exception` without logging the traceback.
- Do not write synchronous SQLAlchemy queries — use `async with session` everywhere.
- Do not create a `.env` file — only `.env.example`. The user will create `.env` themselves.
