# IB Data Configuration Test Files

This directory contains test configuration files to verify that all IB data parameters work correctly.

## Test Configurations

### 1. `minimal_ib_data.yaml`
**Purpose**: Test minimal data fetching (only contract details)

**Use case**: 
- Verify pipeline works with minimal IB API calls
- Test that disabled features don't cause errors
- Useful for debugging connection issues

**What's enabled**:
- Contract details only
- Sector, industry, stock type metadata

**What's disabled**:
- All historical data fetches
- All market snapshots
- All technical indicators
- Benchmark comparison

### 2. `full_ib_data.yaml`
**Purpose**: Test full data fetching (all features enabled)

**Use case**:
- Verify all IB data fetches work together
- Test complete pipeline functionality
- Production-like configuration

**What's enabled**:
- All data fetches
- All technical indicators (ATR, EMA, RSI)
- Volume profiles
- Benchmark comparison
- Pre-market analysis

### 3. `custom_indicators.yaml`
**Purpose**: Test custom parameter values

**Use case**:
- Verify custom ATR/RSI/EMA periods work
- Test extended historical data duration
- Validate custom benchmark symbol

**Custom parameters**:
- ATR period: 20 (instead of 14)
- RSI period: 10 (instead of 14)
- EMA periods: [5, 10, 21, 55, 100] (custom set)
- Daily bars duration: 500 D (extended)
- Volume profile sessions: 5 (instead of 3)
- Benchmark: QQQ (instead of SPY)

## Running Tests

### Unit Tests
```bash
# Run all configuration QA tests
pytest tests/test_config_qa.py -v

# Run specific test class
pytest tests/test_config_qa.py::TestIBDataConfigStructure -v

# Run with coverage
pytest tests/test_config_qa.py --cov=src.config --cov-report=html
```

### Integration Tests with Test Configs

```bash
# Test minimal configuration
python main.py --mode screener --dry-run --no-hours-check

# Test with custom config directory (if you copy test configs)
python main.py --mode screener --config-dir tests/test_configs --dry-run --no-hours-check
```

## Data Source Mapping

Understanding where each output field comes from:

### IB Data (controlled by `ib_data` config)
- **Contract Details**: `symbol`, `company_name`, `sector`, `industry`, `stock_type`
- **Daily Bars**: `prev_close`, `prev_day_high`, `prev_day_low`, `prev_day_open`, `avg_daily_volume_20d`
- **Market Snapshots**: `pre_market_price`, `pre_market_volume`, `pre_market_chg_pct`, `market_cap`, `shares_outstanding`, `beta`, `fifty_two_week_high`, `fifty_two_week_low`
- **Premarket Bars**: `pre_market_high`, `pre_market_low`, `rvol_pre_market`
- **Prev Session VWAP**: `vwap_prev_session`
- **Volume Profile**: `vp_poc`, `vp_vah`, `vp_val`, `vp_lookback_sessions`
- **Benchmark**: `benchmark_symbol`, `benchmark_prev_close`, `benchmark_pre_market_chg_pct`
- **Technical Indicators** (calculated from daily bars):
  - `atr` (Average True Range)
  - `ema_20`, `ema_50`, `ema_200` (Exponential Moving Averages)
  - `rsi_14` (Relative Strength Index)
  - `mc_vol_ratio` (Market Cap / Volume ratio)

### External APIs (controlled by `external_apis` config)
- **yfinance** (always fetched, cannot be disabled): `float_shares`, `next_earnings_date`
- **Financial Modeling Prep** (requires API key): `news_catalysts`

## Validation Checklist

When testing configurations, verify:

- [ ] Pipeline starts without errors
- [ ] Correct log messages for enabled/disabled features
- [ ] No IB API calls for disabled features
- [ ] Output JSON contains expected fields (null for disabled features)
- [ ] Custom parameters are respected (check logs for period values)
- [ ] No crashes when features are disabled
- [ ] Performance is acceptable with full configuration
- [ ] External API fields (float_shares, next_earnings_date) are always present
- [ ] news_catalysts is empty when fmp_api_key is not configured

## Expected Log Output

### Minimal Config
```
INFO  Skipping historical daily bars (fetch_daily_bars=False)
INFO  Skipping market snapshots (fetch_market_snapshot=False)
INFO  Skipping ATR calculation (fetch_atr=False, bars_available=False)
INFO  Skipping pre-market 1-min bars (fetch_pre_market_bars=False)
INFO  Skipping previous-session VWAP (fetch_prev_session_vwap=False)
INFO  Skipping benchmark fetch (fetch_benchmark=False)
INFO  Skipping volume profiles (fetch_volume_profile=False)
```

### Full Config
```
INFO  Fetching 300 D of daily bars for N symbols...
INFO  Calculated ATR for N symbols (period=14)
INFO  Fetching market snapshots for N symbols...
INFO  Fetching pre-market 1-min bars for N symbols...
INFO  Fetching previous-session VWAP for N symbols...
INFO  Benchmark SPY: close=X.XX  chg=+X.XX%
INFO  Fetching volume profiles for N symbols (lookback=3 sessions)...
```

### Custom Indicators
```
INFO  Calculated ATR for N symbols (period=20)
INFO  Fetching 500 D of daily bars for N symbols...
INFO  Benchmark QQQ: close=X.XX  chg=+X.XX%
INFO  Fetching volume profiles for N symbols (lookback=5 sessions)...
```

## Troubleshooting

### Issue: "Missing configuration field"
**Solution**: Ensure all fields in `IBDataConfig` are present in YAML

### Issue: "ATR calculation failed"
**Solution**: Check that `fetch_daily_bars=true` when `fetch_atr=true`

### Issue: "No data in output"
**Solution**: Verify at least `fetch_contract_details` and `fetch_market_snapshot` are enabled

### Issue: "EMA values are null"
**Solution**: Ensure `daily_bars_duration` is long enough for max EMA period (e.g., "300 D" for EMA-200)
