# Stock-Agents

A Python-based multi-agent AI system that processes a list of stock tickers in parallel. Each ticker runs through a configurable pipeline of AI agents, each powered by its own prompt. Everything is driven by configuration — no hardcoded models, no hardcoded agent count.

## Architecture

```
POST /runs (backend:4101)
    └── triggers ai-service:4102
            └── Orchestrator
                    └── Pipeline per ticker (parallel)
                            └── Agent per prompt (parallel or chain)
                                    └── LLM (via litellm)
                                            └── Results → PostgreSQL + ./outputs/
```

- **Backend** (port 4101) — FastAPI REST API for managing runs and reading results
- **AI Service** (port 4102) — FastAPI service that runs the agent pipelines
- **PostgreSQL** — stores run status and all agent outputs
- **LiteLLM** — provider-agnostic LLM routing (OpenAI, Anthropic, Groq, Google, etc.)

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

Edit `Prompts.json` to add, remove, or modify agents. The system reads the number of agents dynamically — no code changes needed. Each key becomes one agent:

```json
{
  "prompt1": "You are a financial data agent...",
  "prompt2": "You are a sentiment analysis agent...",
  "my_custom_agent": "You are a ESG scoring agent..."
}
```

---

## Supported LLM providers

Any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers). Set `LLM_MODEL` and the matching API key in `.env`:

| Provider | Example model string | API key env var |
|----------|---------------------|-----------------|
| Groq (free) | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| Google | `gemini/gemini-pro` | `GOOGLE_API_KEY` |
