1. Stale Hardcoded References (Bug — will break daily)

The prompt is supposed to run every day pre-market, but it hardcodes specific geopolitical situations that will go stale:

- "Trump's May 8 threat" — this is a specifi today (July 2, 2026).
- "US-Iran hostilities in the Strait of Hormuz" — may no longer be the dominant crisis.                           - "Greenland Crisis" — may be resolved or re
                                                                                                                  Fix: Replace the hardcoded "KEY FOCUS AREAS"ions. Something like:
                                                                                                                  KEY FOCUS AREAS ({CURRENTDATE}):
1. MACRO DATA: Identify and analyze the top 3-5 macro data releases in the last 72 hours (CPI, PPI, NFP, GDP, Fed statements, etc.)
2. GEOPOLITICAL RISK: Identify the top active geopolitical crises currently affecting energy, trade, or risk
sentiment.
3. TRADE / TARIFF STATUS: Check for any new tariff announcements, trade deal updates, or retaliatory measures.
4. MARKET INTERNALS: Current VIX level and ton.
5. AI SECTOR: Any major AI earnings, model releases, or capex announcements from the last 72 hours.
6. LABOR MARKET: Any job-related data (NFP,  in the last 72 hours.

This is dynamic — it searches for what's curssuming a specific crisis is ongoing.

---
2. Missing JSON-Only Output Instruction (Bug — breaks parsing)

Your agent.py expects the LLM to return parseable JSON, but the prompt has no instruction to output only JSON. LLMs
will add markdown, preamble, and explanation

Add this at the very end of the prompt:

OUTPUT RULES:
- Respond ONLY with a valid JSON object matching the schema below.
- No markdown, no code fences, no explanatio
- Do not include any text before or after the JSON object.
- All required fields must be present for ev

---
3. Schema Issues

a) risk_on_risk_off should be an enum:

The field is currently a free string. The LLM will return inconsistent values like "risk on", "Risk-On", "risk_on".
Add an enum:

"risk_on_risk_off": {
  "type": "string",
  "enum": ["risk-on", "risk-off", "neutral"]
  "description": "Is the news likely to trigger a risk-on or risk-off market sentiment?"
}

b) brief field description is wrong:

It says "macro news or report related to the2 hours" — this is copy-pasted from the newsagent. There's no "stock" in the macro agent. Fix to: "Concise 1-2 sentence brief on what happened and why it matters
for the market today".

c) summary vs brief are redundant:

summary is "a brief summary highlighting keybrief description. Consider merging them into one field, or make the distinction explicit: summary = what happened (facts), brief = so-what for today's trading
session.

d) No minItems / maxItems on macro_news arra

Without this, the LLM might return 1 item or

"macro_news": {
  "type": "array",
  "minItems": 3,
  "maxItems": 8,
  ...
}

e) Missing top-level aggregate object:

The schema only has a macro_news array (per-item), but no top-level synthesis. The prompt says to produce a "Macro
Tide" report, yet the consuming agent (CEO ooverall regime from array items. Consideradding a top-level field:

"macro_tide": {
  "type": "object",
  "properties": {
    "regime": { "type": "string", "enum": ["l"] },
    "vix_level": { "type": "number" },
    "vix_trend": { "type": "string", "enum":] },
    "spy_futures_direction": { "type": "string", "enum": ["up", "down", "flat"] },
    "overall_market_bias": { "type": "string
    "key_risk_today": { "type": "string" }
  },
  "required": ["regime", "overall_market_bias", "key_risk_today"]
}

This is the "Macro Tide" headline that downs

---
4. {CURRENTDATE} Appears 3 Times Awkwardly

Once in the title section, once as a standalone line under "MISSION", and once in KEY FOCUS AREAS. The standalone line
looks like an accidental copy-paste. Clean iLE and KEY FOCUS AREAS headers.

---
5. QA Section is Vague

"Math Check: Test and verify the math is correct" — there's no math to check in a macro news search. This feels
copy-pasted from another agent. For macro, t

FINAL VERIFICATION:
- Confirm every release_date is within the last 72 hours of {CURRENTDATE}
- Confirm all numeric fields (confidence, susk_off_rate) are within their valid ranges
- Confirm market_price_change_prediction follows the format: "-x.x% to +x.x%"
- Remove any item where the source cannot be

---
6. market_price_change_prediction Format Is Ambiguous

The description says "+x.x% to +x.x%" — both sides are positive. For bearish news this makes no sense. Change the description to "-x.x% to +x.x%" and give  an example: "-0.5% to +0.3%".