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
| Value type | JSON Schema |
|-----------|-------------|
| Text | `{ "type": "string" }` |
| Number (decimal) | `{ "type": "number" }` |
| Number (integer) | `{ "type": "integer" }` |
| True/False | `{ "type": "boolean" }` |
| Text or null | `{ "type": ["string", "null"] }` |
| Number or null | `{ "type": ["number", "null"] }` |
| One of specific values | `{ "type": "string", "enum": ["buy", "hold", "sell"] }` |
| Number in a range | `{ "type": "number", "minimum": 0, "maximum": 1 }` |
| List of text | `{ "type": "array", "items": { "type": "string" } }` |
| Nested object | `{ "type": "object", "properties": { ... } }` |

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

| File | Purpose |
|------|---------|
| `ai_service/agent.py` | Schema injection, validation, retry logic |
| `ai_service/models/llm_client.py` | `response_format={"type":"json_object"}` enforcement |
| `ai_service/schemas/run.py` | `PromptConfig` with `output_schema` and `input_schema` fields |
| `backend/db/models.py` | `Prompt` table with `output_schema` JSONB column |
| `backend/api/routes/runs.py` | `_build_ceo_input_schema()` — auto-computes CEO input schema |
| `backend/api/routes/prompts.py` | CRUD for prompts including `output_schema` |
| `frontend/src/components/PromptDialog.tsx` | UI for editing prompts + output schema textarea + CEO input schema display |
| `ai_service/config.py` | `output_format = "json"` (default) |
