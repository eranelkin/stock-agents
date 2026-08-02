# Output Field Mapping

This document maps each field in the output JSON to its data source and configuration parameter.

## Output Structure

```json
{
  "stocks": [
    {
      "symbol": "AAPL",
      "company_name": "Apple Inc.",
      "sector": "Technology",
      "industry": "Consumer Electronics",
      "market_cap": "3.50T",
      "shares_outstanding": "15.33B",
      "float_shares": "15.20B",
      "beta": 1.25,
      "fifty_two_week_high": 199.62,
      "fifty_two_week_low": 164.08,
      "pre_market_price": 195.50,
      "pre_market_chg": "+2.50%",
      "pre_market_volume": "1.2M",
      "pre_market_high": 196.00,
      "pre_market_low": 194.50,
      "prev_close": 193.00,
      "prev_day_high": 194.00,
      "prev_day_low": 192.00,
      "prev_day_open": 192.50,
      "avg_daily_volume_20d": "50.5M",
      "rvol_pre_market": 1.5,
      "atr": {
        "value": "4.5%",
        "period": 14,
        "timeframe": "1d"
      },
      "ema": {
        "ema_20": 190.50,
        "ema_50": 185.00,
        "ema_200": 175.00
      },
      "rsi_14": 65.5,
      "vwap_prev_session": 193.25,
      "mc_vol_ratio": 69.31,
      "volume_profile": {
        "poc": 193.00,
        "vah": 194.50,
        "val": 191.50,
        "lookback_sessions": 3
      },
      "benchmark": {
        "symbol": "SPY",
        "prev_close": 450.00,
        "pre_market_change_pct": "+0.5%"
      },
      "next_earnings_date": "2026-07-28",
      "news_catalysts": [
        {
          "title": "Apple announces new product",
          "published_date": "2026-07-23T08:00:00Z",
          "url": "https://..."
        }
      ]
    }
  ]
}
```

## Field Mapping Table

| Output Field | Data Source | Config Parameter | Notes |
|-------------|-------------|------------------|-------|
| **Identity** |
| `symbol` | IB Contract Details | `ib_data.fetch_contract_details` | Always required |
| `company_name` | IB Contract Details | `ib_data.fetch_contract_details` | Long name from IB |
| `sector` | IB Contract Details | `ib_data.fetch_sector` | e.g., "Technology", "Healthcare" |
| `industry` | IB Contract Details | `ib_data.fetch_industry` | e.g., "Consumer Electronics" |
| **Market Cap & Shares** |
| `market_cap` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Formatted as "3.50T", "500M", etc. |
| `shares_outstanding` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Total shares issued |
| `float_shares` | yfinance API | Always fetched | Shares available for public trading |
| `beta` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Volatility vs market (1.0 = market) |
| **52-Week Range** |
| `fifty_two_week_high` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Highest price in last 52 weeks |
| `fifty_two_week_low` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Lowest price in last 52 weeks |
| **Pre-Market Data** |
| `pre_market_price` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | Current pre-market price |
| `pre_market_chg` | IB Market Snapshot | `ib_data.fetch_market_snapshot` | % change from prev close |
| `pre_market_volume` | IB Market Snapshot | `ib_data.fetch_volume` | Shares traded in pre-market |
| `pre_market_high` | IB 1-min Bars | `ib_data.fetch_pre_market_bars` | Highest price in pre-market session |
| `pre_market_low` | IB 1-min Bars | `ib_data.fetch_pre_market_bars` | Lowest price in pre-market session |
| **Previous Session Data** |
| `prev_close` | IB Daily Bars | `ib_data.fetch_daily_bars` | Previous regular session close |
| `prev_day_high` | IB Daily Bars | `ib_data.fetch_daily_bars` | Previous session high |
| `prev_day_low` | IB Daily Bars | `ib_data.fetch_daily_bars` | Previous session low |
| `prev_day_open` | IB Daily Bars | `ib_data.fetch_daily_bars` | Previous session open |
| **Volume Metrics** |
| `avg_daily_volume_20d` | IB Daily Bars | `ib_data.fetch_daily_bars` | Average volume over 20 days |
| `rvol_pre_market` | IB 1-min Bars | `ib_data.fetch_pre_market_bars` | Relative volume vs historical avg |
| | | `ib_data.pre_market_rvol_lookback` | Days to look back (default: 20) |
| **Technical Indicators** |
| `atr.value` | Calculated from Daily Bars | `ib_data.fetch_atr` | Average True Range as % |
| `atr.period` | Config | `ib_data.atr_period` | Calculation period (default: 14) |
| `ema.ema_20` | Calculated from Daily Bars | `ib_data.fetch_ema` | 20-period EMA |
| `ema.ema_50` | Calculated from Daily Bars | `ib_data.fetch_ema` | 50-period EMA |
| `ema.ema_200` | Calculated from Daily Bars | `ib_data.fetch_ema` | 200-period EMA |
| | | `ib_data.ema_periods` | List of periods to calculate |
| | | `ib_data.daily_bars_duration` | Must be ≥ max period (e.g., "300 D" for EMA-200) |
| `rsi_14` | Calculated from Daily Bars | `ib_data.fetch_rsi` | Relative Strength Index |
| | | `ib_data.rsi_period` | Calculation period (default: 14) |
| `vwap_prev_session` | IB VWAP Request | `ib_data.fetch_prev_session_vwap` | Volume-weighted average price |
| `mc_vol_ratio` | Calculated | `ib_data.fetch_market_snapshot` | Market cap / avg daily volume |
| | | `ib_data.fetch_daily_bars` | Requires both market cap and volume |
| **Volume Profile** |
| `volume_profile.poc` | IB Volume Profile | `ib_data.fetch_volume_profile` | Point of Control (highest volume) |
| `volume_profile.vah` | IB Volume Profile | `ib_data.fetch_volume_profile` | Value Area High |
| `volume_profile.val` | IB Volume Profile | `ib_data.fetch_volume_profile` | Value Area Low |
| `volume_profile.lookback_sessions` | Config | `ib_data.volume_profile_sessions` | Sessions used (default: 3) |
| **Benchmark Comparison** |
| `benchmark.symbol` | Config | `max_number_of_stocks.benchmark_symbol` | Default: "SPY" |
| `benchmark.prev_close` | IB Market Snapshot | `ib_data.fetch_benchmark` | Benchmark's previous close |
| `benchmark.pre_market_change_pct` | IB Market Snapshot | `ib_data.fetch_benchmark` | Benchmark's pre-market % change |
| **Events & News** |
| `next_earnings_date` | yfinance API | Always fetched | Upcoming earnings date (YYYY-MM-DD) |
| `news_catalysts` | FMP API | `external_apis.fmp_api_key` | Recent news headlines |
| | | `external_apis.news_max_headlines` | Max items per stock (default: 3) |

## Configuration Dependencies

### Required for Basic Output
```yaml
ib_data:
  fetch_contract_details: true  # Minimum requirement
  fetch_market_snapshot: true   # For price data
```

### Required for Technical Analysis
```yaml
ib_data:
  fetch_daily_bars: true        # Required for ATR, EMA, RSI
  daily_bars_duration: "300 D"  # Must be ≥ max(ema_periods)
  fetch_atr: true
  atr_period: 14
  fetch_ema: true
  ema_periods: [9, 20, 50, 200]
  fetch_rsi: true
  rsi_period: 14
```

### Required for Pre-Market Analysis
```yaml
ib_data:
  fetch_pre_market_bars: true
  pre_market_rvol_lookback: 20
  fetch_prev_session_vwap: true
```

### Required for Volume Profile
```yaml
ib_data:
  fetch_volume_profile: true
  volume_profile_sessions: 3
```

### Required for External Data
```yaml
external_apis:
  fmp_api_key: "your_key_here"  # For news_catalysts
  news_max_headlines: 3
  # Note: float_shares and next_earnings_date are always fetched from yfinance
```

## Null Values

When a feature is disabled or data is unavailable, the field will be `null` in the output:

```json
{
  "symbol": "AAPL",
  "atr": {
    "value": null,      // fetch_atr=false or insufficient bars
    "period": 14,
    "timeframe": "1d"
  },
  "ema": {
    "ema_20": null,     // fetch_ema=false or insufficient bars
    "ema_50": null,
    "ema_200": null
  },
  "news_catalysts": []  // fmp_api_key not configured
}
```

## Performance Considerations

Disabling expensive features can significantly reduce runtime:

- `fetch_volume_profile: false` - Saves ~1-2 minutes for 50 stocks
- `fetch_pre_market_bars: false` - Saves ~30-60 seconds for 50 stocks
- `daily_bars_duration: "20 D"` instead of `"300 D"` - Saves ~2-3 minutes
- `fetch_prev_session_vwap: false` - Saves ~30 seconds for 50 stocks

## Example Configurations

See `tests/test_configs/` for complete examples:
- `minimal_ib_data.yaml` - Only contract details
- `full_ib_data.yaml` - All features enabled
- `custom_indicators.yaml` - Custom ATR/EMA/RSI periods
