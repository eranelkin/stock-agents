# Stock-Agents

A Python-based multi-agent AI system that processes a list of stock tickers in parallel. Each ticker runs through a configurable pipeline of AI agents, each powered by its own prompt. Everything is driven by configuration — no hardcoded models, no hardcoded agent count.

## Architecture

### Workflow overview

```
Data.json  [AAPL, GOOGL, MSFT, AMZN, ...]
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                       Orchestrator                      │
│          Splits input → spawns N pipelines in parallel  │
└──────┬──────────────┬──────────────┬──────────────┬─────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
  Pipeline 1     Pipeline 2     Pipeline 3     Pipeline 4
  (AAPL)         (GOOGL)        (MSFT)         (AMZN)
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Per-pipeline internals      │
              │  (identical for each ticker) │
              │                             │
              │    Prompts (from database)   │
              │     prompt1 … promptN       │
              │    (dynamic — no hardcode)  │
              │                             │
              │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
              │  │Agent 1 │  │Agent 2 │  │Agent 3 │  │Agent 4 │
              │  │prompt1 │  │prompt2 │  │prompt3 │  │prompt4 │
              │  │+ LLM   │  │+ LLM   │  │+ LLM   │  │+ LLM   │
              │  └────────┘  └────────┘  └────────┘  └────────┘
              │       ↑ prompt-chain: each agent passes result to next ↓
              │                             │
              │              ┌──────────────▼──────────────┐
              │              │          Aggregator          │
              │              │  merges agent results →      │
              │              │  YAML / JSON output          │
              │              └─────────────────────────────┘
              └─────────────────────────────────────────────┘
                             │  one output file per ticker
                             ▼
              ┌──────────────────────────────────────────────┐
              │           YAML / JSON Reports                │
              │   output_AAPL.yaml, output_GOOGL.yaml …     │
              └──────────────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────────────────────┐
              │          Backend API  (FastAPI)              │
              │    REST endpoints · job queue · auth         │
              └──────────────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────────────────────┐
              │           PostgreSQL  (Docker)               │
              │      runs · results · configs · models       │
              └──────────────────────────────────────────────┘
```

### Component summary

| Component | Port | Role |
|-----------|------|------|
| **Backend** | 4101 | FastAPI REST API — manages runs, prompts, models, and results |
| **AI Service** | 4102 | Runs the orchestrator and all agent pipelines |
| **PostgreSQL** | 5432 | Persists run status, ticker results, prompts, and model configs |
| **LiteLLM** | — | Provider-agnostic LLM routing (OpenAI, Anthropic, Groq, Google, etc.) |

### How a run flows

1. **`Data.json`** supplies the list of tickers (e.g. `AAPL`, `GOOGL`, `MSFT`, `AMZN`).
2. The **Orchestrator** reads the list and spawns one **Pipeline** per ticker, all running concurrently via `asyncio.gather()`.
3. Each **Pipeline** reads **`Prompts.json`** and creates one **Agent** per prompt key — the count is fully dynamic.
4. Agents run in **parallel mode** (all at once) or **chain mode** (each receives the previous agent's output), controlled by `AGENT_MODE` in `.env`.
5. The **Aggregator** merges all agent outputs for a ticker into a single structured result.
6. Results are written to `./outputs/` as YAML or JSON and saved to **PostgreSQL** via the backend API.

---

## Prerequisites

- Python 3.12+
- Docker + Docker Compose (for Docker installation)
- An API key for your chosen LLM provider

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Minimum required values:

```env
# Pick your model (examples below)
LLM_MODEL=groq/llama-3.3-70b-versatile   # Groq (free tier)
# LLM_MODEL=gpt-4o                        # OpenAI
# LLM_MODEL=claude-sonnet-4-6             # Anthropic

# Set the matching API key
GROQ_API_KEY=gsk_your_key_here
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### Free tier note (Groq)

Groq's free tier has a 12K tokens/minute limit. Keep concurrency low to avoid rate limit errors:

```env
MAX_CONCURRENT_PIPELINES=1
MAX_CONCURRENT_AGENTS=2
```

### Agent mode

```env
AGENT_MODE=parallel   # all agents run simultaneously (default)
AGENT_MODE=chain      # each agent receives the previous agent's output
```

---

## Option 1 — Docker Installation

The easiest way to run everything. Starts PostgreSQL, the backend, and the AI service in one command.

### 1. Configure `.env`

Make sure your `.env` has the database and port settings (defaults work out of the box):

```env
POSTGRES_HOST=postgres        # Docker service name, not localhost
POSTGRES_PORT=5432
POSTGRES_DB=stock_agents
POSTGRES_USER=sa_user
POSTGRES_PASSWORD=changeme

BACKEND_PORT=4101
AI_SERVICE_HOST=ai-service    # Docker service name, not localhost
AI_SERVICE_PORT=4102
```

### 2. Build and start

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up --build -d
```

### 3. View logs

```bash
docker compose logs -f ai-service
docker compose logs -f backend
```

### 4. Stop

```bash
docker compose down
```

To also delete the database volume:

```bash
docker compose down -v
```

---

## Option 2 — Local Installation

Run Python services directly on your machine with only PostgreSQL in Docker.

### 1. Install Python dependencies

```bash
pip install -e .
```

### 2. Start PostgreSQL only

```bash
docker compose up postgres -d
```

### 3. Configure `.env`

Use `localhost` instead of Docker service names:

```env
POSTGRES_HOST=localhost
AI_SERVICE_HOST=localhost     # backend calls ai-service via localhost
```

### 4. Start the backend

Open a terminal and run:

```bash
uvicorn backend.main:app --port 4101 --reload
```

### 5. Start the AI service

Open a second terminal and run:

```bash
uvicorn ai_service.main:app --port 4102 --reload
```

---

## Running a job

### Trigger a run

```bash
curl -X POST http://localhost:4101/runs
```

Response:

```json
{
  "id": "905ef4f0-fbc4-4121-8596-9aa8c60c4ccd",
  "status": "pending",
  "created_at": "2026-05-27T12:00:00Z",
  "completed_at": null,
  "error": null
}
```

### Check status

```bash
curl http://localhost:4101/runs/<run_id>
```

Status lifecycle: `pending` → `running` → `completed` | `failed`

### Get results

```bash
curl http://localhost:4101/results/<run_id> | python3 -m json.tool
```

### List all runs

```bash
curl http://localhost:4101/runs
```

---

## Output files

Results are also written to `./outputs/` as YAML or JSON (controlled by `OUTPUT_FORMAT` in `.env`):

```
outputs/
├── output_AAPL.yaml
├── output_GOOGL.yaml
├── output_MSFT.yaml
└── output_AMZN.yaml
```

Example output structure:

```yaml
ticker: AAPL
agents:
  prompt1:
    ticker: AAPL
    price: 189.5
    market_cap: 2900000000000
    pe_ratio: 28.4
    volume_7d_avg: 58000000
  prompt2:
    ticker: AAPL
    sentiment: bullish
    sentiment_score: 0.72
    key_drivers: [...]
    analyst_consensus: buy
  prompt3:
    ticker: AAPL
    trend: uptrend
    rsi_estimate: 62
    macd_signal: bullish
    key_support: 175.0
    key_resistance: 200.0
  prompt4:
    ticker: AAPL
    recommendation: buy
    confidence: 0.8
    time_horizon: medium
    summary: ...
    risk_factors: [...]
    catalysts: [...]
metadata:
  pipeline_duration_ms: 4200
  agent_count: 4
  timestamp: "2026-05-27T12:00:05Z"
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/runs` | Start a new run |
| `GET` | `/runs` | List all runs |
| `GET` | `/runs/{id}` | Get run status |
| `GET` | `/results/{run_id}` | Get all ticker results for a run |
| `GET` | `/health` | Health check |

Interactive docs available at **http://localhost:4101/docs**

---

## Customizing tickers

Edit `Data.json` to change which tickers are processed:

```json
[
  { "name": "AAPL" },
  { "name": "TSLA" },
  { "name": "NVDA" }
]
```

## Customizing agents

Agents are driven by prompts stored in the database with `category = "agents"`. Add, edit, or remove them via the **Prompts tab** in the UI, or directly via the API:

```bash
curl -X POST http://localhost:4101/prompts \
  -H "Content-Type: application/json" \
  -d '{"title": "ESG Agent", "content": "You are an ESG scoring agent...", "category": "agents"}'
```

The system reads the agent count dynamically from the database — no code changes or file edits needed. Each prompt with `category: "agents"` becomes one agent in the pipeline.

---

## Supported LLM providers

Any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers). Set `LLM_MODEL` and the matching API key in `.env`:

| Provider | Example model string | API key env var |
|----------|---------------------|-----------------|
| Groq (free) | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| Google | `gemini/gemini-pro` | `GOOGLE_API_KEY` |
