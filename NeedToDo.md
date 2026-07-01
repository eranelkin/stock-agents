# NeedToDo — Prompt Review & Schema Optimization Context

This file contains everything needed to review, fix, and optimize the existing prompts
after the schema enforcement update. Read this file before touching any prompt.

---

## What We Built (The New System)

We added a 3-layer enforcement system for agent output consistency:

### Layer 1 — Forced JSON at the API Level

Every LLM call now includes `response_format={"type": "json_object"}`.

- For OpenAI (GPT-4o etc.): enforced at the provider level — the model cannot return anything but JSON
- For Claude (Haiku, Sonnet etc.): the model may still add surrounding text, but our parser handles it
- **Location:** `ai_service/models/llm_client.py` — `_call_llm()` function

### Layer 2 — Output Schema Contract per Prompt

Each prompt in the database now has an `output_schema` field (strict JSON Schema format).
At runtime the system:

1. Injects the schema into the agent's system prompt automatically (appended at the end)
2. Validates the LLM response against the schema using `jsonschema.validate()`
3. Retries the LLM call up to 3 times if validation fails
4. Logs a warning and continues if all retries fail (never crashes the pipeline)

- **Location:** `ai_service/agent.py` — `_build_system_prompt()`, `_run_with_schema_retry()`, `_validate_schema()`

### Layer 3 — CEO Input Schema (Auto-Computed)

The CEO agent's input schema is never written by hand. It is automatically computed from
the output schemas of all currently active "agents" category prompts. The structure is:

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "agents": {
      "type": "object",
      "properties": {
        "<Stock Agent Title>": { ...that agent's output_schema... }
      }
    }
  }
}
```

- **Location (runtime):** `backend/api/routes/runs.py` — `_build_ceo_input_schema()`
- **Location (UI display):** `frontend/src/components/PromptDialog.tsx` — auto-shown when editing CEO prompts

---

## How the System Prompt Is Built at Runtime

The final system prompt sent to the LLM is constructed as follows:

```
<your prompt content — behavior instructions only>

--- INPUT SCHEMA — what you will receive ---
{ ...auto-computed input schema if CEO agent... }
---

--- OUTPUT SCHEMA — respond ONLY with a JSON object that matches this schema exactly. No explanation, no text before or after, no markdown. Pure JSON only. ---
{ ...your output_schema... }
---
```

**What this means for prompt writing:**

- The prompt content should contain ONLY behavior instructions
- Do NOT include format instructions in the prompt text ("respond with JSON", "use this schema", etc.) — the system injects those automatically
- Do NOT paste the output schema into the prompt text — the system injects it automatically
- Do NOT write "no markdown" or "no explanation" — the system injects that too

---

## Pipeline Data Flow

```
Data.json  →  Stock Agents (parallel or chain)  →  Stock Aggregator  →  CEO Agent
```

### What Stock Agents Receive (Input)

Every stock agent receives the contents of `Data.json` for one ticker:

```json
{
  "name": "AAPL",
  "sector": "Information Technology"
  // ...any extra fields you add to Data.json
}
```

In chain mode, each agent also receives:

```json
{
  "previous_output": { ...output of the previous agent... }
}
```

### What the CEO Agent Receives (Input)

The CEO agent receives the merged output of ALL active stock agents:

```json
{
  "name": "AAPL",
  "agents": {
    "Technical Analysis Agent": { ...that agent's output... },
    "News Sentiment Agent":     { ...that agent's output... },
    "Fundamental Data Agent":   { ...that agent's output... }
  }
}
```

The key names inside `agents` are the exact **titles** of your stock agent prompts.

---

## Output Schema Rules (Strict JSON Schema Format)

Every output schema must be valid JSON Schema Draft 7 (the standard supported by `jsonschema` library).

### Required Structure

```json
{
  "type": "object",
  "properties": {
    "field_name": { "type": "string" }
  },
  "required": ["field_name"]
}
```

### Type Cheatsheet

| Value type             | JSON Schema                                             |
| ---------------------- | ------------------------------------------------------- |
| Text                   | `{ "type": "string" }`                                  |
| Number (decimal)       | `{ "type": "number" }`                                  |
| Number (integer)       | `{ "type": "integer" }`                                 |
| True/False             | `{ "type": "boolean" }`                                 |
| Text or null           | `{ "type": ["string", "null"] }`                        |
| Number or null         | `{ "type": ["number", "null"] }`                        |
| One of specific values | `{ "type": "string", "enum": ["buy", "hold", "sell"] }` |
| Number in a range      | `{ "type": "number", "minimum": 0, "maximum": 1 }`      |
| List of text           | `{ "type": "array", "items": { "type": "string" } }`    |
| Nested object          | `{ "type": "object", "properties": { ... } }`           |

### What to Put in `required`

Only add a field to `required` if the agent MUST return it every time. Fields the agent
might not always know should be typed as `["number", "null"]` and left out of `required`.

---

## Prompt Writing Rules (After This Update)

### What a Good Stock Agent Prompt Looks Like

```
You are a [role description] agent.

You will receive a JSON object with a stock ticker symbol and sector.

Your task: [What to analyze / what to return].

Rules:
- [Behavior rule 1]
- [Behavior rule 2]
- If a value is unknown or unavailable, use null.
- Never fabricate data. Use your training knowledge only.
```

**Do NOT add:**

- ❌ "Respond ONLY with a valid JSON object"
- ❌ "No explanation, no markdown"
- ❌ "Use this exact schema: { ... }"
- ❌ Any format or structure instructions
- ❌ Any copy of the output schema fields in the prompt text

The system adds all of the above automatically.

### What a Good CEO Agent Prompt Looks Like

```
You are a [role description] agent.

You will receive a JSON object containing a stock ticker symbol and the outputs
of all stock analysis agents under the "agents" key.

Your task: [What synthesis to perform / what to return].

Rules:
- Base your analysis only on the data provided in the agents field.
- [Behavior rule 2]
- [Behavior rule 3]
```

**Do NOT add:**

- ❌ Any description of what the input looks like ("you will receive ticker, price, RSI...") — the input schema is auto-injected and always up to date
- ❌ Any output format instructions — auto-injected
- ❌ Any copy of the schema fields — auto-injected

---

## Checklist: How to Review Each Existing Prompt

For every stock agent prompt, check:

- [ ] **Output Schema exists** — is there a valid JSON Schema in the `output_schema` field?
- [ ] **All important fields are in the schema** — every field the CEO or downstream system needs must be declared
- [ ] **Types are correct** — numbers as `number`, not `string`; nullable fields use `["type", "null"]`
- [ ] **Required fields are set** — at minimum `ticker` should be in `required`
- [ ] **Prompt text has no format instructions** — remove any "respond with JSON", schema copy-paste, or "no markdown" text
- [ ] **Prompt text has no schema definition** — the schema lives in the `output_schema` field, not in the prompt text
- [ ] **Prompt text focuses on behavior** — who is the agent, what to analyze, what rules to follow

For the CEO agent prompt, additionally check:

- [ ] **Output schema exists** — CEO needs its own output schema too
- [ ] **Prompt text refers to `agents` key** — "you will receive the outputs under the `agents` key"
- [ ] **Open the Edit dialog** — verify the "What this agent receives" block shows all active stock agents with their schemas
- [ ] **Field names match** — if the CEO prompt references field names from stock agents (e.g. "use the `rsi_estimate` field"), those field names must exist in the stock agent's output schema

---

## Output Files Format

All output files are now written as **JSON** (changed from YAML):

- `stock_AAPL.json` — per-ticker stock pipeline output
- `agg_AAPL.json` — aggregated output (all stock agent outputs merged per ticker)
- `CEO_AAPL.json` — CEO agent output per ticker

---

## Key Files Reference

| File                                       | Purpose                                                                                   |
| ------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `ai_service/agent.py`                      | Schema injection, validation, retry logic                                                 |
| `ai_service/models/llm_client.py`          | `response_format={"type":"json_object"}` enforcement                                      |
| `ai_service/schemas/run.py`                | `PromptConfig` with `output_schema` and `input_schema` fields                             |
| `ai_service/pipeline_registry.py`          | Registers all pipeline types (stocks, sectors, macro) — add new types here                |
| `ai_service/config.py`                     | Data file paths (`mocks/Data.json` etc.) and all runtime settings                         |
| `backend/db/models.py`                     | `Prompt` table with `output_schema` JSONB column                                          |
| `backend/api/routes/runs.py`               | `_build_ceo_input_schema()` + loads and injects input schemas for all agent types         |
| `backend/api/routes/prompts.py`            | CRUD for prompts + schema endpoints (`/ticker-schema`, `/sector-schema`, `/macro-schema`) |
| `backend/stock_schema.json`                | Field glossary injected into every stock agent prompt                                     |
| `backend/sector_schema.json`               | Field glossary injected into every sector agent prompt                                    |
| `backend/macro_schema.json`                | Field glossary injected into every macro agent prompt (placeholder — fill when ready)     |
| `mocks/Data.json`                          | Ticker input data for stock pipeline                                                      |
| `mocks/Sectors.json`                       | Sector input data for sectors pipeline                                                    |
| `mocks/Macro.json`                         | Macro input data for macro pipeline (placeholder — fill when ready)                       |
| `frontend/src/components/PromptDialog.tsx` | Prompt edit dialog — shows "What this agent receives" for stocks, sectors, macro, and CEO |

---

## NEW: Ticker Input Schema System

A global file `backend/stock_schema.json` now describes every field in the ticker object (Data.json). This is automatically injected into the system prompt of every stock agent and sector agent at runtime, so the AI understands what each key means precisely.

### Rules for this file

- **When you add a new field to `Data.json`** → you MUST also add it to `backend/stock_schema.json` with a `description`. Otherwise the AI will see the value but not understand what it means.
- Each entry must include `"type"` and `"description"` at minimum.
- The file is loaded once when the backend starts. Restart the backend after editing it.

### Do I need a new schema file for each new agent type?

**One schema file per unique input data shape.** The rule:

| Agent type      | Status                | Schema file                                                                                        | Data file                  |
| --------------- | --------------------- | -------------------------------------------------------------------------------------------------- | -------------------------- |
| Stock agents    | ✅ Done               | `backend/stock_schema.json`                                                                        | `mocks/Data.json`          |
| Sector agents   | ✅ Done               | `backend/sector_schema.json`                                                                       | `mocks/Sectors.json`       |
| Macro agents    | ✅ Done (placeholder) | `backend/macro_schema.json`                                                                        | `mocks/Macro.json`         |
| Any future type | Follow same pattern   | Create `backend/<type>_schema.json`, add entry in `pipeline_registry.py`, load schema in `runs.py` | Create `mocks/<Type>.json` |

### What it looks like in the agent's system prompt

At runtime, this block is automatically appended to every stock agent's instructions:

```
--- INPUT SCHEMA — what you will receive ---
{
  "title": "TickerInput",
  "properties": {
    "atr": {
      "type": "number",
      "description": "Average True Range over the last 14 trading days, in USD..."
    },
    ...
  }
}
---
```

### UI

When you open a stock agent prompt in the UI, a read-only **"What this agent receives"** block is shown below the output schema textarea. It displays the content of `backend/stock_schema.json` live. Use it as a reference while writing prompts.

---

## NEW: Add `description` to Output Schema Properties

This is a writing task — no code change needed. Every time you define or update an output schema for a stock agent in the UI, add a `description` line to each property.

**Why:** The CEO agent receives the outputs of all stock agents. Without descriptions, the CEO sees raw values like `"rsi_estimate": 45.3` with no explanation. With descriptions, the CEO's system prompt includes a full glossary of every field it receives — automatically.

### How to write it

Instead of:

```json
"rsi_estimate": { "type": "number", "minimum": 0, "maximum": 100 }
```

Write:

```json
"rsi_estimate": {
  "type": "number",
  "minimum": 0,
  "maximum": 100,
  "description": "RSI between 0-100. Above 70 = overbought (likely to drop), below 30 = oversold (likely to rise)."
}
```

### Rule of thumb for descriptions

- State the **unit** (USD, percent, days, etc.)
- State the **range or valid values** if relevant
- State **what it means** in plain English — not just the abbreviation

### Which agents need this

Every active stock agent that has an output schema. The CEO agent's output schema also benefits from descriptions for the same reason.

---

## Updated Checklist: Before Every Run

### .env file

- [ ] `OUTPUT_FORMAT=json` is set (not `yaml`)
- [ ] `AGENT_MODE=parallel` (default) or `chain` depending on what you want to test
- [ ] Correct `LLM_MODEL` is set

### Data files (in `mocks/` folder)

- [ ] `mocks/Data.json` — contains the tickers you want to process
- [ ] Every field key in the ticker objects exists in `backend/stock_schema.json` with a description
- [ ] `mocks/Sectors.json` — only matters if you have active Sector prompts
- [ ] `mocks/Macro.json` — only matters if you have active Macro prompts (currently a placeholder)

### Stock Agent Prompts (in the UI)

- [ ] Output schema exists and is valid JSON Schema
- [ ] **Every property in the output schema has a `description`** — so the CEO understands it
- [ ] Required fields include at minimum `ticker`
- [ ] Prompt text contains behavior instructions only — no format instructions, no schema copy-paste
- [ ] Open the Edit dialog → verify the "What this agent receives" block shows the ticker field glossary

### CEO Agent Prompt (in the UI)

- [ ] Output schema exists with descriptions on every property
- [ ] Open the Edit dialog → verify the "What this agent receives" block shows ALL active stock agents with their schemas
- [ ] If the CEO prompt references specific field names (e.g. `rsi_estimate`), confirm those field names exist in the relevant stock agent's output schema

### After Adding New Data.json Fields

- [ ] Add the new field to `backend/stock_schema.json` with `type` and `description`
- [ ] Restart the backend so the file is reloaded

---

_Last updated: 2026-06-22 (sectors + macro wired up; data files moved to mocks/; schema path bug fixed)_


- output_schema - Try to update the flow dynamically with the file content. Read the files on run time.
- alert in the logs for the last running proccess, meaning if news agent did  not fetch any post, need to color red.
- retry if not succeed and the response empty/no news for the symbol (news agent).