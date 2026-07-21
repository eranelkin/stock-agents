Deep Analysis — Intraday Technical-Analysis Agent
1. What the system is actually trying to do
Run at pre-market, take a thin static snapshot of one ticker, and emit a forecast intraday trade setup (entry/TP/SL/timing + squeeze/institutional context) as strict JSON. The output is a prediction, not a measurement.

That framing exposes the single most important truth about this design, which everything below rotates around:

The prompt demands institutional-grade microstructure math (Order Flow Imbalance via Cont-Kukanov-Stoikov, Volume Profile POC/VAH/VAL, liquidity sweeps, FVGs, VWAP reclaim, live $TICK/$ADD, time-adjusted RVOL) — but supplies the model with 8 scalar fields and a web browser. None of those techniques are computable from the inputs, and none are reliably obtainable by web search at pre-market. So the model has only one way to satisfy the contract: fabricate the numbers. The elaborate formulas create an illusion of rigor while guaranteeing invented order-flow data.

2. Prompt analysis (core findings)
Capability–requirement mismatch (fatal). OFI, volume profile, sweeps, FVG, anchored VWAP, and $TICK/$ADD all require tick/L2 or intraday OHLCV arrays. The model has none. It will hallucinate them with false precision.
Forecast vs. measurement contradiction. "MISSION FAILURE IF YOU PULL WRONG / NOT UP-TO-DATE DATA" is impossible to honor pre-market — today's intraday data does not exist yet. The prompt conflates "predict today" with "verify today's live data."
Field-name mismatch. Prompt "locks" pre_market_price, pre_parket_volume (typo), market_cap, atr; the input JSON uses "pre-market price", "Pre-market vol", "Market cap", "ATR". The anchoring instruction silently fails to bind — this is likely a real source of the "accuracy mistakes" you're seeing.
No abstain path. The schema required forces a fully-populated setup per stock. There is no "no A+ setup today / stand aside" outcome, so the model manufactures a trade even when none qualifies — directly contradicting "focus only on A+ setups."
ATR is ambiguous. ATR 11.61 on a $62.63 stock ≈ 18.5% daily range. Period/timeframe undefined, yet SL distance and position sizing depend entirely on it. This poisons every risk number downstream.
Unrealistic triangulation rule. "<2% variance across 3 sources" is fine for price but wrong for short float (updates bi-monthly), institutional holdings (quarterly 13F), and impossible for live $TICK.
Bull-only structural logic. Every formula (sweep, FVG) is bullish; no bearish/short variants and no direction field — invalid for real day trading.
Prompt bloat / grandiosity. "top 0.02%", "neurosymbolic", repeated "close by end of day" — burns tokens and nudges the model toward overconfident fabrication rather than calibrated abstention.
3. Input-schema analysis
Inconsistent keys/casing; unit-embedded strings ("15.57B", "781K") force error-prone parsing — send numerics.
mc_vol_ratio: 19940.0 — undefined meaning/units.
No true TA inputs at all: no prev-day H/L/C, no VWAP, no EMAs, no avg volume, no float, no SPY reference. The agent is asked to do TA with no TA data.
price (62.63) vs pre-market price (63.47) unlabeled — which is prior close? (Math checks: 63.47/62.63 ≈ +1.34%, consistent, but should be explicit.)
4. Output-schema analysis
Good: additionalProperties:false everywhere; bounded confidence/success_probability/squeeze_risk; date pattern.
Gaps: No grade (A+/B/C) despite the entire rubric being about grading. No direction (long/short). No risk_reward_ratio though EV/sizing are computed. No numeric level fields (entry/TP/SL/VWAP/POC are all free-text strings → not machine-usable, not validatable). No no_trade/abstain flag. confidence vs success_probability are undifferentiated. Date format DD-MM-YYYY is unusual for US markets and must match {CURRENTDATE} injection.
5. Improvements Table (ranked)
#	Priority	Area	Problem	Recommended fix
1	🔴 Critical	Prompt logic	Demands OFI/volume-profile/sweeps/$TICK on data the model lacks → fabrication	Either feed the required data via API (see §6) or downgrade these to "compute only if the corresponding array is present in input; otherwise output null + lower confidence." Never ask for OFI without L2 data.
2	🔴 Critical	Anti-hallucination	No explicit ban on inventing metrics	Add hard rule: "If a metric cannot be derived from provided inputs or verified via ≥2 sources, output null/\"unknown\" and reduce confidence. Fabrication = mission failure." Add a data_provenance/per-field confidence concept.
3	🔴 Critical	Input binding	Prompt field names ≠ JSON keys (pre_parket_volume typo, casing)	Normalize both sides to identical snake_case keys; fix typo; explicitly map each locked field to its exact JSON key.
4	🔴 Critical	Schema	No abstain path → forced fabrication of setups	Add grade enum (A+/B/C/no_trade) and allow empty/no_trade items; instruct "return no_trade when no A+ confluence exists."
5	🔴 Critical	Framing	"verify up-to-date data" impossible pre-market (forecast)	Reframe explicitly as a pre-market probabilistic forecast for the coming session; separate "static facts to verify" from "levels to project."
6	🔴 Critical	Risk math	ATR period/timeframe undefined; drives SL + sizing	Require atr_period + atr_timeframe in input; validate ATR/price sanity (flag if >~10% daily).
7	🟡 Mid	Schema	No direction; formulas bull-only	Add direction (long/short); provide bearish sweep/FVG variants.
8	🟡 Mid	Schema	confidence vs success_probability overlap	Define crisply: confidence = analyst conviction in the read; success_probability = modeled P(TP before SL).
9	🟡 Mid	Schema	Levels buried in free-text strings	Add numeric fields: entry_low/high, tp, sl, vwap, poc, support, resistance, risk_reward_ratio. Keep prose fields for narrative only.
10	🟡 Mid	Prompt	Triangulation "<2%" wrong for slow-moving fields	Per-field tolerance: price ~0.2%, short float/institutional = "most recent reported value + as-of date."
11	🟡 Mid	Prompt	$TICK/$ADD not knowable pre-market	Remove as inputs; label as "assess at/after open" or drop from pre-market scope.
12	🟡 Mid	Schema	Missing risk_reward_ratio though EV/sizing computed	Add it; require R:R ≥ configurable min for A+.
13	🟢 Low	Input	Unit strings "15.57B", "781K"	Send numeric (15_570_000_000, 781000).
14	🟢 Low	Input	mc_vol_ratio undefined	Document formula/units or remove.
15	🟢 Low	Prompt	LaTeX formulas (model doesn't execute LaTeX)	Convert to plain pseudocode; state "reason step-by-step, then verify arithmetic."
16	🟢 Low	Output	Time fields lack timezone	Require ET/timezone suffix on entry_time/tp_time.
17	🟢 Low	Prompt	Grandiosity + repetition ("0.02%", repeated close-by-EOD)	Trim; replace hype with concrete acceptance criteria.
18	🟢 Low	Output	date DD-MM-YYYY unusual for US	Confirm it matches {CURRENTDATE} format; consider ISO YYYY-MM-DD.
6. Parameters to pull from API and pass as input
Priority = importance of it being a trusted API input rather than left to the model's web search. HIGH = the model cannot reliably get it by search, or the technical math is impossible without it.

Parameter	Description	Why it's needed	API-input priority
intraday_ohlcv_bars (1m/5m, prior N=10–20 sessions)	Historical minute bars, per day	Prerequisite for RVOL, liquidity sweeps, FVG, order blocks, VWAP, volume profile — none computable without it	🔴 HIGH (foundational)
prev_close	Prior regular-session close	Anchor for gap %, chg %, direction	🔴 HIGH
prev_day_high / prev_day_low	Prior day range	Primary intraday S/R and breakout refs	🔴 HIGH
premarket_high / premarket_low	Pre-market session extremes	Key opening levels for entries/sweeps	🔴 HIGH
avg_daily_volume_20d	20-day average volume	Denominator/baseline for RVOL	🔴 HIGH
vwap (prior session + anchored)	Volume-weighted avg price	Prompt's core "A+ = VWAP reclaim" trigger	🔴 HIGH
volume_profile (POC/VAH/VAL)	Volume-at-price distribution	Phase-3 requirement; not web-searchable	🔴 HIGH
ema_20 / ema_200 (daily)	Trend EMAs	Explicit bias-determination rule	🔴 HIGH
atr_value + atr_period + atr_timeframe	ATR with defined window	SL distance + position sizing integrity	🔴 HIGH
spy_prices (prev close + premarket)	Index reference	Required for RS vs SPY calc	🔴 HIGH
float_shares	Free-float share count	Defines short-float meaning + squeeze	🔴 HIGH
next_earnings_date	Upcoming earnings/report	Catalyst + avoid trading into event risk	🔴 HIGH
short_float_pct	% of float short	Squeeze scoring; stale/unreliable via search	🟡 MED
short_ratio_days_to_cover	Days to cover	Squeeze dynamics	🟡 MED
institutional_holding_pct	Institutional ownership	Reason_3 / conviction; quarterly 13F, API cleaner	🟡 MED
rsi_14	Momentum oscillator	Overbought/oversold context	🟡 MED
news_catalysts_24h	Recent headlines/feed	Catalyst gating for A+ grade	🟡 MED (search viable but API better)
52w_high / 52w_low	Yearly extremes	Positioning context	🟡 MED
shares_outstanding	Total shares	Clarifies market cap / mc_vol_ratio	🟢 LOW
beta	Volatility vs market	Sizing/regime context	🟢 LOW
sector / industry	Classification	Peer/regime alignment	🟢 LOW
$TICK / $ADD	Live market internals	Genuinely useful, but cannot exist pre-market	🟢 LOW (defer to open)
level2_order_book / tick quotes	Bid/ask depth	Only true source for OFI — realistically unavailable; if absent, OFI must be dropped, not faked	🔴 HIGH if OFI kept, else remove requirement
Bottom line
The prompt's biggest risk isn't wording — it's that it asks for computations it cannot feed. Two coherent paths:

Path A (recommended): make it a real quant agent. Supply the HIGH-priority API fields (bars, VWAP, volume profile, EMAs, SPY, float, ATR spec). Then the formulas become executable instead of decorative.
Path B: make it an honest forecaster. Strip the microstructure/OFI/$TICK demands, add the no_trade/grade abstain path and the null-when-unknown rule, and let it produce a calibrated probabilistic projection from the limited data — explicitly labeled as such.
Either way, fixes #1–#6 are prerequisites to trusting a single number this thing outputs.

Want me to (a) rewrite the full prompt in the corrected form, (b) produce the upgraded input + output JSON schemas, or (c) both?