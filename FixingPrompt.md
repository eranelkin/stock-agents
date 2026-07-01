# Fixing the Technical Analysis Agent Prompt

A simple explanation of what is wrong and how to fix it.

---

## Problem 1: The "Expert Persona" Does Not Actually Help

**What the prompt does:**
It says "You are the Elite Lead Institutional Intraday Strategy Analyst (John Murphy)."

**What is wrong — in simple words:**
Imagine you hire someone to fix your sink. You say "pretend you are the world's greatest plumber who ever lived." Does that make them fix the sink better? No. They either know how to fix the sink or they don't.

Same with AI. Calling it "Elite" and "Institutional" and naming a famous real person does nothing useful. Worse — the AI "knows" who John Murphy is from books he wrote. So it starts thinking like a book author, not an intraday trader.

**How to fix it:**
Skip the fancy title. Just tell the AI exactly what job it needs to do. Example: "You are a technical analyst. Your job is to look at the data I give you and decide if there is a good trade setup or not."

---

## Problem 2: The AI Will Give You the Wrong Format — Every Time

**What the prompt does:**
It asks for an "Executive Summary Table."

**What is wrong — in simple words:**
Your system is a pipeline. Think of it like an assembly line. Each worker (agent) passes a box to the next worker. The box must be a specific size and shape — in your case, JSON format (a specific way of organizing data that computers can read).

Your prompt is telling the AI to hand over a table — like something you would see in a Word document. The next worker on the assembly line cannot process a Word document. The line breaks.

Also, the prompt uses math formulas written in a special academic format. The AI sometimes copies that style into its answer, which makes the output even more unreadable by your system.

**How to fix it:**
Tell the AI exactly what shape the box must be. Show it the exact fields you want. End the prompt with: "Reply ONLY with a JSON object. No tables. No explanations. Nothing outside the JSON."

---

## Problem 3: The AI Is Making Up All the Numbers — And You Do Not Know It

**This is the most dangerous problem.**

**What the prompt does:**
It tells the AI to "execute live web searches" and "cross-reference 3 websites" and "monitor live market data like $TICK and $ADD."

**What is wrong — in simple words:**
Your AI has no internet connection. It cannot visit websites. It cannot see live stock prices. It cannot check today's market data.

So what does it do when you tell it to? It pretends. It makes up numbers that sound realistic and presents them as real. Confidently. With no warning.

Imagine asking someone who is locked in a windowless room: "What is the weather outside right now?" They cannot know. But if you insist they answer, they will guess — and they will say it like they are sure.

That is exactly what your AI is doing with every $TICK reading, every RVOL calculation, every short float percentage. It is inventing those numbers.

**For a trading tool, this is genuinely dangerous.** A setup graded "A+" might be based entirely on made-up data.

There is also a small typo in the prompt: `{CURRENT*DATE}` has an asterisk instead of an underscore. That means the date never actually gets inserted. The AI just sees the text `{CURRENT*DATE}` literally, every single time.

**How to fix it:**
Before the AI runs, your system (or a separate data-fetching step) must collect all the real numbers — live price, volume, VWAP, market internals, news — and put them directly into the input JSON. The AI's job is to think about numbers, not fetch them. You bring it the numbers; it does the analysis.

---

## Problem 4: The AI Has No Idea Where It Sits in the Pipeline

**What the prompt does:**
Nothing. It does not tell the AI that it is one of several agents working together.

**What is wrong — in simple words:**
Imagine a relay race. Runner 1 finishes and passes a baton to Runner 2. Runner 2 should know: "I am receiving a baton, I need to run my leg, then pass it to Runner 3."

Your AI (Agent 3 of 4) has no idea:
- What Agent 2 (the sentiment agent) already figured out and passed to it
- What Agent 4 (the final recommendation agent) is expecting to receive from it

So it ignores the previous agent's work and produces output in whatever format it feels like — which may be completely unusable by the next agent.

**How to fix it:**
Add a few lines at the top of the prompt that say: "You are Agent 3 of 4. Agent 2 already analyzed sentiment and gave you these fields: [list them]. Your job is to do technical analysis and hand your result to Agent 4, which needs these exact fields: [list them]."

---

## Problem 5: Half the Words in the Prompt Do Nothing

**What the prompt does:**
It uses a lot of dramatic language: "CRITICAL," "MISSION WILL BE DECLARED A FAILURE," "ELITE," "NEUROSYMBOLIC FINAL VERIFICATION," "MANDATORY." The day-trading rule ("close all positions by end of day") is written three separate times.

**What is wrong — in simple words:**
Think of the AI like a very smart employee reading your instructions. If you write "CRITICAL CRITICAL CRITICAL IMPORTANT URGENT" before every single sentence, they stop treating any of it as special. It all becomes noise.

Also, long complicated math formulas cost tokens — which means they cost money and make the response slower. And since the AI cannot actually run those formulas (it does not have the raw data), they are purely decorative. They look impressive in the prompt but do nothing.

**How to fix it:**
Say things once, clearly. Cut anything that is repeated. Cut the dramatic warnings — they do not make the AI more accurate. Remove the math formulas and replace them with plain rules like: "If today's volume is more than double the normal volume, that is a strong signal."

---

## Summary

Your prompt was written for a chatbot that has internet access and can browse websites in real time. But your system is an API pipeline with no internet access. So every "live" number the AI gives you — every market reading, every volume ratio, every sentiment signal — is invented. The prompt also never says "give me JSON," so your pipeline cannot reliably read the output. And since the agents do not know they are part of a team, they do not coordinate.

**The fix in four steps:**

1. Fetch real data before the agent runs
2. Pass all that data in the input JSON
3. Tell the agent exactly what format to output
4. Tell the agent where it sits in the chain (which agent came before, which comes after)

---

---

# Fixing the News Agent Prompt

A simple explanation of what is wrong and how to fix it.

---

## Problem 1: The Prompt Only Covers Half the Output — The AI Has No Instructions for the Other Half

**What the prompt does:**
It tells the AI to find news, identify catalysts, and verify sources.

**What is wrong — in simple words:**
Your output schema has six top-level sections. Your prompt only talks about one of them — the news analysis part. Three entire sections are completely missing from the instructions:

- `ceo_impact_assessment` — what does this news mean for the company's operations?
- `price_prediction` — where will the price go today, and what is the expected range?
- `actionable_next_steps` — what specific actions should the trader take?

It is like hiring a chef and telling them only how to make the salad. They show up, make a beautiful salad, and put it on the plate. But you also needed soup and a main course. Nobody told them. The plate is half empty.

The AI will either skip those sections entirely — which breaks your pipeline — or it will guess at what to put there with no guidance, which means the numbers will be unreliable.

**How to fix it:**
Add a dedicated instruction block for each missing section. For `price_prediction`, tell the AI to use the `pre_market_price` from the input as the anchor for `expected_open`, and use the `atr` field from the input to calculate the expected trading range. For `ceo_impact_assessment`, tell the AI to summarize the operational and macro effects in 1-2 sentences each. For `actionable_next_steps`, tell the AI to write 3-5 specific, concrete trader actions — not generic advice.

---

## Problem 2: The AI Will Fabricate Every Link It Gives You

**This is a silent data quality problem that is very hard to catch.**

**What the prompt does:**
It asks the AI to include a `url` for every news article it finds. The output schema marks this field as required.

**What is wrong — in simple words:**
AI models cannot browse the internet. When you ask them for a URL, they construct one that looks plausible — the right domain, the right format, a headline that sounds real — but the link goes nowhere. It is a made-up address.

Imagine asking someone to give you a phone number for a restaurant they have never called. They will give you a number that looks like a phone number. But when you dial it, nobody answers.

Now imagine that fake phone number gets stored in your database, passed to the CEO agent, and eventually shown to a trader who tries to verify a news story. They click the link. 404 error. Or worse — a completely different article.

The schema description even says "if available," but then the schema also marks the field as required. That is a contradiction in the schema itself, and it guarantees inconsistent behavior.

**How to fix it:**
Add an explicit rule: "Only include a URL if it was returned directly in a web search result. If you cannot confirm the exact URL, write `URL_NOT_CONFIRMED` in that field. Never construct or guess a URL." Also fix the schema contradiction — either remove `url` from the `required` list, or change the description to match the fact that it is required.

---

## Problem 3: The AI Does Not Know What Format the Dates Should Be In

**What the prompt does:**
It says to find the "earliest recorded release" of each news item.

**What is wrong — in simple words:**
Your output schema requires all date fields to be in a very specific format: `2026-06-30T09:30:00Z`. This is called ISO 8601. But your prompt never mentions this format anywhere.

So the AI will write dates however it feels like — "June 30, 2026," or "6/30/26," or "Yesterday at 9:30 AM." Your pipeline then tries to read a date in that strict format, finds something different, and either crashes or stores a broken value.

**How to fix it:**
Add one line to the prompt: "All date and time fields must use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ. If the exact time is unknown, use T00:00:00Z."

---

## Problem 4: The AI Does Not Know How to Calculate the Sentiment Score

**What the prompt does:**
It says to classify sentiment as Bullish, Bearish, or Neutral.

**What is wrong — in simple words:**
Your output schema also requires a `sentiment_score` — a number between -1.0 and 1.0. But the prompt never explains how to calculate it. The AI has to invent a number.

This matters because the `sentiment_score` is what other agents and the CEO will use to make decisions. If one run returns 0.3 and another run on the same news returns 0.7, the downstream agents will behave differently for no reason. There is no consistency.

**How to fix it:**
Give the AI a simple rule to follow internally — for example: each confirmed bullish catalyst adds between 0.15 and 0.30 to the score depending on how important it is; each bearish catalyst subtracts the same. A single-source rumor counts for no more than 0.05 in either direction. The final score is clamped between -1.0 and 1.0. The sentiment label must match: score above 0.1 means Bullish, below -0.1 means Bearish, anything in between means Neutral.

---

## Problem 5: The AI Is Told to Show Its Work — Which Breaks the Output

**What the prompt does:**
It ends with: "Math Check: Test and verify the math is correct. QA the numbers in each point and make sure the numbers are correct."

**What is wrong — in simple words:**
When you tell the AI to "verify the math," it writes out the verification as text — paragraphs of checking and confirming — before or after the JSON. Your pipeline then receives text plus JSON instead of just JSON, and it cannot parse the result.

Think of it like asking a baker to "verify the cake is ready." You want them to check it in the oven quietly and then hand you the cake. Instead, they write you a three-paragraph report about how they checked the temperature, how the toothpick came out clean, and why they are confident it is done — and then hand you the report along with the cake. You just wanted the cake.

**How to fix it:**
Replace the QA section with a silent checklist. Tell the AI: "Before outputting, silently verify: all dates are ISO 8601, sentiment_score matches the sentiment label, summary_points has exactly 3 items per article, all required fields are populated. Then output ONLY the JSON. No verification text."

---

## Problem 6: The AI Does Not Know the Rules for Each News Article

**What the prompt does:**
It says to find news articles and compile them into reports.

**What is wrong — in simple words:**
Your output schema is very specific about what goes inside each news article object. It requires exactly 3 `summary_points` — no more, no fewer. But the prompt never mentions this. The AI will sometimes write 1, sometimes 5, depending on how much it has to say. This breaks schema validation.

The prompt also never explains what those 3 points should cover. The schema description says they should represent "the quantitative, structural, and predictive aspects." But that instruction lives only in the schema, which the AI never sees during a live run.

**How to fix it:**
Add this rule directly to the prompt: "Each news article must include exactly 3 summary_points. Point 1: a specific number, percentage, or metric from the article. Point 2: what this means for the company's business or structure. Point 3: the likely short-term market impact."

---

## Problem 7: The Input Field Names Do Not Match the Output Field Names — And Nobody Explains the Difference

**What the prompt does:**
Nothing. It does not mention the input fields at all.

**What is wrong — in simple words:**
Your input JSON has a field called `price` — described as the most recent closing price. Your output schema has a field called `previous_close`. These are the same number, but they have different names.

Your AI receives the input with the name `price`. It needs to write the output with the name `previous_close`. But nobody told it they are the same thing. So it will either search for the previous close externally (getting a potentially different or fabricated value), or it will skip the field, or it will get confused.

Similarly, your `price_prediction` section needs the `atr` and `pre_market_price` from the input to calculate ranges and expected open — but the prompt never says to use those fields for that purpose.

**How to fix it:**
Add a short field mapping section to the prompt: "`context.previous_close` = use the `price` field from the input JSON exactly as given. `price_prediction.expected_open` = use the `pre_market_price` field from the input as your starting anchor. `estimated_trading_range` = use the `atr` field from the input to calculate the expected high and low."

---

## Problem 8: The Output Instruction Is Missing Entirely

**What the prompt does:**
Nothing. There is no section at the end that says "return JSON" or describes the expected output format.

**What is wrong — in simple words:**
Same core problem as the technical agent. The AI will do all the analysis, then write it out as paragraphs and headers and bullet points — not as the JSON your pipeline needs.

**How to fix it:**
Add this block at the very end of the prompt, after everything else:

```
OUTPUT — MANDATORY
Your response must be a single raw JSON object only.
No text before {. No text after }. No markdown. No headers. No explanations.
The object must match the TickerIntelligencePack schema exactly.
Your response starts with { and ends with }. Nothing else.
```

---

## Summary — News Agent

Your news prompt covers only the research and discovery part of the job. It says nothing about price prediction, CEO impact assessment, or actionable steps — which are three of the six required output sections. It also never tells the AI to return JSON, never specifies date formats, never explains the sentiment score formula, and never sets the rule that each article needs exactly 3 summary points.

The URL fabrication problem is the most dangerous issue — the AI will invent links that look real but do not exist, and those fake links will flow silently through your pipeline into the CEO agent and eventually in front of a trader.

**The fix in five steps:**

1. Add an instruction block for every output section — including `price_prediction`, `ceo_impact_assessment`, and `actionable_next_steps`
2. Map the input field names to the output field names explicitly (`price` → `previous_close`, etc.)
3. Add the URL integrity rule — only use URLs returned directly from a search result
4. Specify the date format, the sentiment score formula, and the 3-point summary rule
5. End the prompt with a JSON-only output instruction
