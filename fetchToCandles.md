# Fetch → Candlestick Pipeline (Porting Guide)

Scope: **only** how OHLCV candle data gets from Yahoo Finance into a rendered
lightweight-charts candlestick chart, at a specific frequency/interval, in
this repo. Indicators, strategy backtesting, auth, drawings, AI trends, etc.
are intentionally excluded — copy this doc into the new repo as the spec for
rebuilding just this pipeline.

This reflects the **current** code in `stockchart-simulator` (not the old
generic README that used to live in this file, which described a different,
outdated architecture — SQLite/Highcharts/port 4001. The real stack is
**Postgres + lightweight-charts v5**).

---

## 1. Data source

Raw candles come from Yahoo Finance's public (undocumented) chart endpoint:

```
https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range}
```

- No API key required.
- `symbol` — ticker, e.g. `AAPL`, `SPY`, or an index like `^SPX`.
- `interval` — Yahoo's bar size string: `1m`, `2m`, `5m`, `15m`, `30m`, `1h`,
  `1d`, `1wk`, `1mo`.
- `range` — Yahoo's lookback window string: `8d`, `10d`, `15d`, `20d`, `8mo`,
  `5y`, `10y`, `15y`, etc. Yahoo rejects incompatible interval/range combos
  (e.g. you can't ask for `1m` interval over a `5y` range — intraday data is
  only retained for a short window).

Fetched with plain `fetch` (Node 18+ has it built in; this repo uses
`node-fetch` since it predates that):

```js
// server/src/services/yahoo.service.js
export const fetchMarketData = async (symbol, interval, range) => {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=${interval}&range=${range}`;
  const response = await fetch(url);
  const data = await response.json();
  if (!data.chart.result) {
    throw new Error("Invalid symbol or parameters");
  }
  const result = data.chart.result[0];
  return formatYahooData(result, interval);
};
```

Yahoo's raw response shape (relevant parts):

```json
{
  "chart": {
    "result": [{
      "timestamp": [1700000000, 1700003600, ...],   // seconds, one per bar
      "indicators": {
        "quote": [{
          "open":   [150.2, ...],
          "high":   [152.1, ...],
          "low":    [149.8, ...],
          "close":  [151.5, ...],
          "volume": [54000000, ...]
        }]
      }
    }]
  }
}
```

---

## 2. Frequency → range mapping

The frequency/interval the user picks in the UI drives **three** separate
lookup tables server-side (`server/src/constants/ranges.js`):

```js
// Full fetch range per interval — used when there's no cached data yet
export const RANGE_BY_FREQUENCY = {
  "1m": "8d",
  "2m": "10d",
  "5m": "10d",
  "15m": "15d",
  "30m": "20d",
  "1h": "8mo",
  "1d": "5y",
  "1wk": "10y",
  "1mo": "15y",
};

// Short refresh range — just enough to catch new/updated candles
export const REFRESH_RANGE = {
  "1m": "2d",
  "2m": "14d",
  "5m": "3d",
  "15m": "5d",
  "30m": "7d",
  "1h": "5d",
  "1d": "1mo",
  "1wk": "3mo",
  "1mo": "6mo",
};

// How long to serve from DB before re-hitting Yahoo, per interval.
// Proportional so 1m charts stay near-live while 1d charts don't
// hit Yahoo on every symbol switch.
export const COOLDOWN_MS = {
  "1m": 30_000,
  "2m": 45_000,
  "5m": 60_000,
  "15m": 2 * 60_000,
  "30m": 3 * 60_000,
  "1h": 5 * 60_000,
  "1d": 10 * 60_000,
  "1wk": 30 * 60_000,
  "1mo": 60 * 60_000,
};
```

**Important gotcha:** the client also has its own copy of this table in
`client/src/constants/theme.js` and sends it as a `range` query param, but
the server **ignores that query param entirely** — the server always
recomputes the range itself from `RANGE_BY_FREQUENCY[interval]`. If you port
this, either delete the client-side table + query param (dead code) or make
the server actually trust it — don't leave both silently duplicated like
this repo does (the two copies have already drifted: client has `"2m": "14d"`,
server has `"2m": "10d"`).

---

## 3. Formatting raw Yahoo data into candles

`server/src/utils/formatData.js` turns Yahoo's parallel arrays into an array
of candle objects, and cleans up two real problems Yahoo's API has:

```js
const INTRADAY_INTERVALS = new Set(['1m', '2m', '5m', '15m', '30m', '1h']);

export const formatYahooData = (result, interval = '1d') => {
  const timestamps = result.timestamp;
  const quotes = result.indicators.quote[0];

  const candles = timestamps
    .map((t, i) => ({
      time: t * 1000, // seconds → ms
      open: quotes.open?.[i],
      high: quotes.high?.[i],
      low: quotes.low?.[i],
      close: quotes.close?.[i],
      volume: quotes.volume?.[i],
    }))
    .filter((c) => {
      if (
        !Number.isFinite(c.open) ||
        !Number.isFinite(c.high) ||
        !Number.isFinite(c.low) ||
        !Number.isFinite(c.close)
      ) {
        return false; // Yahoo returns nulls for holes (e.g. halted symbol)
      }
      // Drop flat candles (open===high===low===close) — usually junk bars
      const isFlat = c.open === c.high && c.high === c.low && c.low === c.close;
      return !isFlat;
    });

  // For daily+ intervals, Yahoo sometimes returns two entries for the same
  // calendar day (midnight UTC for the historical bar + market-open UTC for
  // the in-progress current bar). Dedupe by calendar day, keep the LAST
  // entry (most up to date), and normalize the timestamp to midnight UTC —
  // this keeps daily candle timestamps stable/consistent regardless of what
  // time of day the fetch happened.
  if (!INTRADAY_INTERVALS.has(interval)) {
    const byDay = new Map();
    for (const c of candles) {
      const day = new Date(c.time).toISOString().slice(0, 10);
      byDay.set(day, c);
    }
    return [...byDay.values()].map((c) => ({
      ...c,
      time: new Date(new Date(c.time).toISOString().slice(0, 10) + 'T00:00:00.000Z').getTime(),
    }));
  }

  return candles; // intraday: keep raw per-bar timestamps as-is
};
```

Output: `{ time: <ms epoch>, open, high, low, close, volume }[]`, ascending
by time (Yahoo already returns them in order).

---

## 4. Caching layer (optional but recommended)

This repo caches candles in Postgres to avoid re-hitting Yahoo on every
symbol/frequency switch. **You can skip this entirely** for a simpler port
(just call `fetchMarketData` directly on every request) — but if you want
the caching behavior, here's how it works.

### Schema

```sql
CREATE TABLE IF NOT EXISTS candles (
  symbol   TEXT             NOT NULL,
  interval TEXT             NOT NULL,
  ts       BIGINT           NOT NULL,   -- ms epoch, matches formatYahooData's `time`
  open     DOUBLE PRECISION NOT NULL,
  high     DOUBLE PRECISION NOT NULL,
  low      DOUBLE PRECISION NOT NULL,
  close    DOUBLE PRECISION NOT NULL,
  volume   DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (symbol, interval, ts)
);
CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles (symbol, interval, ts);
```

### Repository (`server/src/db/candle.repository.js`)

- `getCandles(symbol, interval, sinceMs)` — `SELECT ... WHERE symbol=$1 AND interval=$2 AND ts>=$3 ORDER BY ts ASC`
- `getLatestTimestamp(symbol, interval)` — `SELECT MAX(ts)`, used to decide if the DB has anything at all
- `upsertCandles(symbol, interval, candles)` — batched `INSERT ... ON CONFLICT (symbol, interval, ts) DO UPDATE` inside a transaction (`BEGIN`/`COMMIT`, rollback on error). Conflict target is the composite primary key, so re-fetching an overlapping range just overwrites existing rows instead of erroring.

### Service (`server/src/services/candle.service.js`) — the actual caching decision tree

```js
const lastFetchedAt = new Map(); // in-memory, per (symbol|interval), resets on server restart

export const getCandlesForSymbol = async (symbol, interval) => {
  const cacheKey = `${symbol}|${interval}`;
  const fullRange = RANGE_BY_FREQUENCY[interval] ?? "5y";
  const sinceMs = rangeToSinceMs(fullRange);
  const latestTs = await repo.getLatestTimestamp(symbol, interval);

  if (latestTs === null) {
    // 1. Nothing in DB yet → full historical fetch, persist, return
    const candles = await fetchMarketData(symbol, interval, fullRange);
    await repo.upsertCandles(symbol, interval, candles);
    lastFetchedAt.set(cacheKey, Date.now());
    return repo.getCandles(symbol, interval, sinceMs);
  }

  const lastFetched = lastFetchedAt.get(cacheKey);
  const cooldown = COOLDOWN_MS[interval] ?? 5 * 60_000;
  if (lastFetched && Date.now() - lastFetched < cooldown) {
    // 2. Fetched recently → serve straight from DB, no Yahoo call
    return repo.getCandles(symbol, interval, sinceMs);
  }

  // 3. Cooldown expired → short incremental refresh (REFRESH_RANGE, not
  //    the full range), upsert over existing rows, return from DB
  const refreshRange = REFRESH_RANGE[interval] ?? "1mo";
  const fresh = await fetchMarketData(symbol, interval, refreshRange);
  await repo.upsertCandles(symbol, interval, fresh);
  lastFetchedAt.set(cacheKey, Date.now());
  return repo.getCandles(symbol, interval, sinceMs);
};
```

`rangeToSinceMs("5y")` etc. converts a Yahoo-style range string to an
absolute "now minus X" ms timestamp, used to bound the DB read:

```js
export const rangeToSinceMs = (range) => {
  const num = parseInt(range, 10);
  const unit = range.replace(/[0-9]/g, "");
  const now = Date.now();
  switch (unit) {
    case "m":  return now - num * 60_000;
    case "d":  return now - num * 86_400_000;
    case "mo": return now - num * 30 * 86_400_000;
    case "y":  return now - num * 365 * 86_400_000;
    default:   return null;
  }
};
```

A `getCandlesDirectFromYahoo(symbol, interval)` bypass also exists — fetches
straight from Yahoo with no DB read/write at all, for a "force live" mode.

---

## 5. API endpoint

`GET /api/market?symbol=SPY&interval=1d[&useDb=false|&strictDb=true]`

```js
// server/src/controllers/market.controller.js
export const getMarketData = async (req, res) => {
  const { symbol = "SPY", interval = "1d", useDb, strictDb } = req.query;
  let candles;
  if (strictDb === "true") {
    // DB-only, no Yahoo fallback — used when another process (a batch sync
    // job) is expected to have already populated the DB
    const sinceMs = rangeToSinceMs(RANGE_BY_FREQUENCY[interval] ?? "5y");
    candles = getCandles(symbol, interval, sinceMs);
  } else if (useDb === "false") {
    candles = await getCandlesDirectFromYahoo(symbol, interval); // no caching
  } else {
    candles = await getCandlesForSymbol(symbol, interval); // default: cached path
  }
  res.json(candles);
};
```

Response body: `[{ time, open, high, low, close, volume }, ...]` (ms epoch
timestamps, ascending).

Minimal version for a fresh repo (no DB at all):

```js
router.get("/market", async (req, res) => {
  const { symbol = "SPY", interval = "1d" } = req.query;
  const range = RANGE_BY_FREQUENCY[interval] ?? "5y";
  const candles = await fetchMarketData(symbol, interval, range);
  res.json(candles);
});
```

---

## 6. Client: fetching + frequency state

`client/src/contexts/MarketDataContext.js` holds `currentSymbol` and
`currentFrequency` in React state, and refetches whenever either changes:

```js
const fetchData = useCallback(async () => {
  const url = `${API_BASE}/api/market?symbol=${currentSymbol}&interval=${currentFrequency}`;
  const response = await fetch(url).then((res) => res.json());
  const data = parseDailyToOHLCObject(response);
  data.frequency = currentFrequency; // stash it — needed later for LWC time formatting
  setChartData(data);
}, [currentSymbol, currentFrequency]);

useEffect(() => { fetchData(); }, [fetchData]);
```

`API_BASE` comes from `REACT_APP_API_BASE_URL` (CRA env var, defaults to
`http://localhost:4001`/whatever port the server runs on).

`parseDailyToOHLCObject` (`client/src/utils/chart.utils.js`) reshapes the
JSON array response into the `{ ohlc: [...], volume: [...] }` shape the rest
of the client code expects, and sorts ascending by time defensively:

```js
export function parseDailyToOHLCObject(data, { sortAscending = true } = {}) {
  const ohlc = [];
  const volume = [];
  for (const item of data) {
    const ts = Number(item.time);
    ohlc.push([ts, Number(item.open), Number(item.high), Number(item.low), Number(item.close)]);
    volume.push([ts, Number(item.volume)]);
  }
  if (sortAscending) {
    ohlc.sort((a, b) => a[0] - b[0]);
    volume.sort((a, b) => a[0] - b[0]);
  }
  return { ohlc, volume };
}
```

Note the intermediate format is a **tuple array** `[ts, o, h, l, c]`, not
objects — a holdover from an earlier Highcharts-based version of this app.
If you're building fresh against lightweight-charts only, you could skip
straight to `{time, open, high, low, close}` objects and drop this
intermediate step. It's kept here because other parts of this codebase
(indicators, tooltips) also consume the tuple form.

---

## 7. Client: converting to lightweight-charts format

This is the part that's easy to get wrong. **lightweight-charts requires
different `time` formats depending on bar size**:

- Daily/weekly/monthly bars → `'YYYY-MM-DD'` **string**. LWC uses this to
  handle weekend/holiday gaps natively (it just skips days with no bar).
- Intraday bars (minutes/hours) → **integer unix seconds**. LWC treats the
  time axis as continuous seconds and will render gaps if you use a date
  string here — you want the raw timestamp instead.

```js
// client/src/utils/chart.utils.js
export const toLWTime = (timestampMs, frequency) => {
  if (frequency === '1d' || frequency === '1wk' || frequency === '1mo') {
    const d = new Date(timestampMs);
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, '0');
    const day = String(d.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  return Math.floor(timestampMs / 1000);
};

export const toOHLCsLW = (ohlcArrays, frequency) =>
  ohlcArrays.map(([ts, open, high, low, close]) => ({
    time: toLWTime(ts, frequency),
    open, high, low, close,
  }));

export const toVolumeLW = (volumeArrays, ohlcArrays, frequency) =>
  volumeArrays.map(([ts, value], i) => ({
    time: toLWTime(ts, frequency),
    value,
    color: (ohlcArrays[i]?.[4] ?? 0) >= (ohlcArrays[i]?.[1] ?? 0)
      ? "#26a69a"   // close >= open → bull color
      : "#ef5350",  // close < open  → bear color
  }));
```

All date math uses `getUTC*` — don't use local-time getters here, or the
candle will shift by your machine's timezone offset relative to what the
server stored (server normalizes daily candles to UTC midnight, see §3).

---

## 8. Client: rendering the candlestick + volume series

`client/src/components/StockChart.jsx` — the minimal slice relevant to
candles/volume (the file also does indicators, drawings, tooltips, which are
out of scope here):

```js
import { createChart, CandlestickSeries, HistogramSeries } from "lightweight-charts";

const chart = createChart(container, { width, height, /* ...theme options */ });

const candleSeries = chart.addSeries(CandlestickSeries, {
  upColor: "#09FB07",
  downColor: "#E1354D",
  borderUpColor: "#09FB07",
  borderDownColor: "#E1354D",
  wickUpColor: "#787b86",
  wickDownColor: "#787b86",
});

const volumeSeries = chart.addSeries(HistogramSeries, {
  priceFormat: { type: "volume" },
  priceScaleId: "volume",
});
chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });

// Whenever chartData changes:
const dataFreq = chartData.frequency || currentFrequency;
candleSeries.setData(toOHLCsLW(chartData.ohlc, dataFreq));
volumeSeries.setData(toVolumeLW(chartData.volume, chartData.ohlc, dataFreq));

// Optional: keep the view scrolled to the most recent N bars instead of
// zooming to fit the entire history every time new data loads
const windowSize = 150;
if (chartData.ohlc.length > windowSize) {
  const lw = toOHLCsLW(chartData.ohlc, dataFreq);
  chart.timeScale().setVisibleRange({
    from: lw[lw.length - windowSize].time,
    to: lw[lw.length - 1].time,
  });
} else {
  chart.timeScale().fitContent();
}
```

`lightweight-charts` **requires data passed to `setData` to be sorted
ascending by time** — this is why both the server (Yahoo already returns
ascending) and the client (`parseDailyToOHLCObject`'s defensive sort) care
about ordering.

---

## 9. Porting checklist for the new repo

Minimal (no caching):
1. `npm install express cors` (server); native `fetch` is fine on Node 18+, skip `node-fetch`.
2. Copy §3's `formatYahooData` + the intraday interval set.
3. Copy §2's `RANGE_BY_FREQUENCY` table (only the full-range one — skip `REFRESH_RANGE`/`COOLDOWN_MS` if you're not caching).
4. One route: `GET /api/market?symbol=&interval=` → `fetchMarketData` → `formatYahooData` → `res.json(candles)`.
5. Client: `npm install lightweight-charts`.
6. Copy `toLWTime`, `toOHLCsLW`, `toVolumeLW` from §7 verbatim — the UTC-string-vs-unix-seconds split is the one thing that will silently misrender if you reimplement it from memory.
7. `createChart` + `addSeries(CandlestickSeries, ...)` + `addSeries(HistogramSeries, ...)` as in §8, `setData` on symbol/frequency change.

If you also want the Postgres caching layer, additionally port §4 (schema +
repository + service) and wire the controller per §5's three-mode branch —
but it's genuinely optional complexity; skip it unless you're hitting
Yahoo's rate limits in practice.

### Gotchas to remember
- Server ignores the client's `range` query param — don't let the two frequency→range tables drift out of sync if you keep both (better: single source of truth, one side computes it).
- Daily+ candle timestamps are normalized to UTC midnight and deduped per calendar day server-side — don't re-dedupe or re-normalize on the client.
- Flat OHLC candles (all four values equal) are dropped as Yahoo junk — don't treat a legitimately flat trading day as invalid if you loosen this filter.
- LWC time format depends on frequency (`YYYY-MM-DD` string for `1d`/`1wk`/`1mo`, integer unix seconds otherwise) — get this backwards and the chart either shows unwanted weekend gaps on intraday data or misaligned bars on daily data.
- Index symbols need a `^` prefix for Yahoo (e.g. `^SPX` for S&P 500, `^DJI` for Dow) — make sure your symbol-search/autocomplete UI passes that through correctly.
