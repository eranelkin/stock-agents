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
