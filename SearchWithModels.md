# Search, Models & Prompts — Simple Guide

---

## 1. What is Tavily?

Tavily is an external web search service — think of it as Google, but designed specifically for AI systems.

Your system does **not** use the model's built-in knowledge to get current stock prices, news, or pre-market data. That knowledge is frozen at the model's training cutoff. Instead, **every time a run happens**, your system calls Tavily to fetch live data from the internet.

**Tavily is always the search engine in this system.** The AI model decides *what to search* (in tool_call mode), but Tavily is always the one actually going to the internet.

> You need a Tavily API key (`TAVILY_API_KEY` in `.env`) and `SEARCH_ENABLED=true` for any search to work.

---

## 2. The Two Search Modes

### Prefetch mode

**Simple version:** Your system searches the web first, then hands the results to the model.

```
[Your system] → search Tavily → get results → [LLM call with results attached]
```

- One single LLM call
- You control what gets searched (via the Search Query Template)
- Lower token usage — conversation history never grows
- Faster response overall
- Best when you always need the same kind of data

### Tool call mode

**Simple version:** The model searches the web itself, multiple times, during its thinking process.

```
[LLM call] → model says "I need to search" → Tavily search → results returned to model
           → model says "I need another search" → Tavily search → results returned
           → model says "I need another search" → ... (up to SEARCH_MAX_TOOL_ROUNDS)
           → model finally writes the answer
```

- Multiple LLM calls in a loop
- The model decides what to search and when — you don't control this
- **Every round re-sends the full conversation history** — token usage grows fast
- Example: 8 rounds on a long prompt = ~18,000 prompt tokens (vs ~5,000 in prefetch)
- Best when the model needs to explore and follow up on what it finds

---

## 3. Key Settings Explained

| Setting | What it does | Where to set it |
|---|---|---|
| `SEARCH_ENABLED` | Master on/off switch for all search | `.env` |
| `SEARCH_MODE` | Global default: `prefetch` or `tool_call` | `.env` |
| `TAVILY_API_KEY` | Your Tavily account key | `.env` |
| `SEARCH_MAX_RESULTS` | How many web results Tavily returns per search call | `.env` |
| `SEARCH_MAX_TOOL_ROUNDS` | Max number of search loops in tool_call mode before forcing a final answer | `.env` |
| Search Mode (per prompt) | Override the global mode for one specific prompt | Prompts UI → Edit |
| Enable Search (per prompt) | Turn search on/off for one specific prompt | Prompts UI → Edit |
| Search Query Template | The exact query sent to Tavily in prefetch mode | Prompts UI → Edit |

---

## 4. Search Query Template

This is only used in **prefetch mode**.

It is the exact sentence sent to Tavily as a search query. You write it once, and every time a run happens the `{ticker}` placeholder is replaced with the actual stock symbol.

**Example:**
```
Template:  {ticker} pre-market price short interest today
POET run:  POET pre-market price short interest today      ← sent to Tavily
TSLA run:  TSLA pre-market price short interest today      ← sent to Tavily
```

**If you leave the template empty,** the system falls back to a default:
```
{ticker} stock latest news research 2026
```

**Tips for writing a good template:**
- Be specific — Tavily returns better results with targeted queries
- Add "today" or "pre-market" to prioritize fresh data
- Include what you actually need: price, short interest, news, catalysts
- Keep it under 10–12 words — longer queries don't always return better results

---

## 5. Your Prompts — What Each One Does

### Technical (day trading agent)
Produces the Executive Summary with entry/exit levels, confidence, squeeze risk, etc. This is your **main trading decision prompt**. It needs: current price, pre-market data, short interest, ATR, recent news.

### News (catalyst news agent)
Finds the most important news from the last 24–72 hours that will move the stock price today. It needs: news headlines, sources, publication times, price impact assessment.

### Fundamental (fundamental analyst)
Analyzes earnings quality, cash flow, moat, institutional positioning. It needs: recent earnings releases, SEC filings, financial metrics.

### Sector (macro/sector agent)
Analyzes the broader sector (e.g. Technology, Healthcare) and gives an intraday prediction score. It needs: sector ETF data, macro catalysts, options flow context.

### CEO (decision agent)
Receives the outputs from all other agents and makes the final trading decision. **It does not need web search** — it reasons from what the other agents already produced.

---

## 6. Recommendations — Model + Search Mode per Prompt

### Technical
- **Search mode:** `prefetch`
- **Why:** You always need the same data (price, short interest, news). The model doesn't need to decide what to search — you know exactly what's needed. Switching from `tool_call` to `prefetch` reduces tokens from ~18,000 to ~5,000 per run.
- **Query template:** `{ticker} pre-market price short interest intraday catalysts today`
- **Best model:** Claude Sonnet or GPT-4o — they follow complex structured output instructions (the 22-field YAML) more reliably than smaller models. If cost is a concern, use a capable open model like Llama 3.3 70B via Groq.

### News
- **Search mode:** `tool_call`
- **Why:** News discovery benefits from the model following leads — if it finds a press release, it may need a second search to cross-reference it. The model drives this better than a fixed query.
- **Best model:** Any fast model works here — Groq/Llama 3.3 70B is a good choice. The output structure is simpler than Technical.

### Fundamental
- **Search mode:** `prefetch`
- **Why:** You need specific financial data. One targeted search for recent earnings/filings is more efficient than letting the model wander.
- **Query template:** `{ticker} earnings report SEC filing financial results last 7 days`
- **Best model:** Claude Sonnet or GPT-4o — fundamental analysis requires careful reasoning from financial data.

### Sector
- **Search mode:** `prefetch`
- **Why:** Sector data is predictable — you always want the same ETF pre-market data and macro context. One clean search is enough.
- **Query template:** `{sector ETF} sector pre-market outlook catalysts today` — note: sectors use a different input schema, so you'd customize this per sector.
- **Best model:** GPT-4o or Claude Sonnet — the output schema is complex (18 fields with mathematical constraints).

### CEO
- **Search mode:** **disabled** (`SEARCH_ENABLED = false` for this prompt)
- **Why:** The CEO agent receives the already-researched outputs from all other agents. It doesn't need internet access — it needs strong reasoning to synthesize and decide.
- **Best model:** Claude Opus or GPT-4o — this is a pure reasoning task. Use your most capable model here even if it's slower, because this is the final decision.

---

## 7. Quick Decision Guide

```
Does my prompt need live internet data?
  └── No  → Disable search entirely (CEO agent, any synthesis/aggregation prompt)
  └── Yes → Do I always know exactly what I need to search?
              └── Yes → Use PREFETCH + write a Search Query Template
              └── No  → Use TOOL_CALL (model explores on its own)
                        └── Set SEARCH_MAX_TOOL_ROUNDS low (3–5) to control token usage
```

---

## 8. Token Cost Reality Check

This is why search mode matters for your bill:

| Scenario | Approx. prompt tokens per ticker |
|---|---|
| No search | ~2,000–4,000 |
| Prefetch (1 search, results injected) | ~4,000–6,000 |
| Tool call, 3 rounds | ~8,000–10,000 |
| Tool call, 8 rounds (your last run) | ~18,000+ |
| Tool call, 10 rounds | ~25,000+ |

With 5 tickers in a run, tool_call at 8 rounds = ~90,000 prompt tokens per run. Prefetch for the same 5 tickers = ~25,000. Same quality of information, 65% fewer tokens.
