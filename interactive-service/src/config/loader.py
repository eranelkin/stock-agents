from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import dacite
import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class IBGatewayConfig:
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 1
    timeout: int = 30


@dataclass
class PacingConfig:
    historical_delay_seconds: float = 0.6
    contract_details_delay_seconds: float = 0.1
    market_data_delay_seconds: float = 0.1
    max_concurrent_mkt_data: int = 50
    historical_request_timeout_seconds: float = 45.0


@dataclass
class OutputConfig:
    directory: str = "./output"
    filename_prefix: str = "premarket"


@dataclass
class PreMarketConfig:
    check_hours: bool = True
    tz: str = "America/New_York"


@dataclass
class CronConfig:
    day_of_week: str = "mon-fri"
    hour: int = 8
    minute: int = 0
    timezone: str = "America/New_York"


@dataclass
class SchedulerConfig:
    enabled: bool = False
    mode: str = "screener"
    cron: CronConfig = field(default_factory=CronConfig)


@dataclass
class IBDataConfig:
    fetch_contract_details: bool = True
    fetch_daily_bars: bool = True
    fetch_market_snapshot: bool = True
    fetch_pre_market_bars: bool = True
    fetch_prev_session_vwap: bool = True
    fetch_volume_profile: bool = False
    atr_period: int = 14
    ema_periods: List[int] = field(default_factory=lambda: [9, 20, 50, 200])
    ema_timeframe: str = "1d"
    rsi_period: int = 14
    beta_timeframe: str = "1Y daily"
    daily_bars_duration: str = "300 D"
    pre_market_rvol_lookback: int = 20
    volume_profile_sessions: int = 3

    # Output Fields ────────────────────────────────────────────────────────────
    # Contract Details
    output_company_name: Optional[str] = "ibk"
    output_sector: Optional[str] = "ibk"
    output_industry: Optional[str] = "ibk"
    output_stock_type: Optional[str] = "ibk"
    
    # Daily Bars Data
    output_prev_close: Optional[str] = "ibk"
    output_prev_chg_pct: Optional[str] = "ibk"
    output_prev_day_high: Optional[str] = "ibk"
    output_prev_day_low: Optional[str] = "ibk"
    output_prev_day_open: Optional[str] = "ibk"
    
    # Market Snapshot Data
    output_pre_market_price: Optional[str] = "ibk"
    output_pre_market_chg_pct: Optional[str] = "ibk"
    output_market_cap: Optional[str] = "ibk"
    output_shares_outstanding: Optional[str] = "ibk"
    output_beta: Optional[str] = "ibk"
    output_fifty_two_week_high: Optional[str] = "ibk"
    output_fifty_two_week_low: Optional[str] = "ibk"
    output_bid_ask: Optional[bool] = True # This one can remain Optional[bool] as it's not a source choice
    
    # Volume Data (from various sources)
    output_pre_market_volume: Optional[str] = "ibk"
    output_avg_daily_volume_20d: Optional[str] = "ibk"
    
    # Pre-market Bars Data
    output_pre_market_high: Optional[str] = "ibk"
    output_pre_market_low: Optional[str] = "ibk"
    output_rvol_pre_market: Optional[str] = "ibk"
    
    # Previous Session VWAP
    output_vwap_prev_session: Optional[str] = "ibk"
    
    # Volume Profile Data
    output_vp_poc: Optional[str] = "ibk"
    output_vp_vah: Optional[str] = "ibk"
    output_vp_val: Optional[str] = "ibk"
    
    # Benchmark (SPY) Data
    output_benchmark_data: Optional[str] = "ibk"
    output_benchmark_prev_close: Optional[str] = "ibk"
    output_benchmark_pre_market_chg_pct: Optional[str] = "ibk"
    
    # Technical Indicators
    output_atr: Optional[str] = "ibk"
    output_ema: Optional[str] = "ibk"
    output_rsi: Optional[str] = "ibk"


@dataclass
class ExternalApisConfig:
    fmp_api_key: str = ""       # Financial Modeling Prep key — free at financialmodelingprep.com
    finnhub_api_key: str = ""   # Finnhub.io key — free at finnhub.io (60 calls/min)
    news_max_headlines: int = 3  # max news items returned per stock (0 to disable)
    output_news_catalysts: Optional[str] = "yfinance"
    output_float_pct: Optional[str] = "yfinance"
    output_next_earnings_date: Optional[str] = "yfinance"
    output_short_float_pct: Optional[str] = "yfinance"
    output_short_ratio: Optional[str] = "yfinance"
    output_institutional_holding_pct: Optional[str] = "yfinance"


@dataclass
class StockAgentsConfig:
    """Integration settings for auto-triggering a stock-agents run after output is written."""
    enabled: bool = False
    backend_url: str = "http://localhost:4101"
    run_name_prefix: str = "IBK Pre-Market"
    enrichment_enabled: bool = False
    candle_frequency: str = "1d"
    model_names: List[str] = field(default_factory=list)  # empty = all active models


@dataclass
class AppConfig:
    ib_gateway: IBGatewayConfig = field(default_factory=IBGatewayConfig)
    pacing: PacingConfig = field(default_factory=PacingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    pre_market: PreMarketConfig = field(default_factory=PreMarketConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    ib_data: IBDataConfig = field(default_factory=IBDataConfig)
    external_apis: ExternalApisConfig = field(default_factory=ExternalApisConfig)
    stock_agents: StockAgentsConfig = field(default_factory=StockAgentsConfig)
    max_number_of_stocks: int = 70
    benchmark_symbol: str = "SPY"


@dataclass
class ScannerBatch:
    market_cap_min_usd: Optional[float] = None
    market_cap_max_usd: Optional[float] = None


@dataclass
class ScreenerConfig:
    scan_code: str = "TOP_PERC_GAIN"
    instrument: str = "STK"
    location_code: str = "STK.US.MAJOR"
    number_of_rows: int = 50
    market_cap_min_usd: Optional[float] = None
    market_cap_max_usd: Optional[float] = None
    avg_volume_min: Optional[int] = None
    exclude_etfs: bool = True
    atr_min: Optional[float] = None
    price_min: Optional[float] = None
    pre_market_vol_min: Optional[float] = None
    pre_market_chg_pct_min: Optional[float] = None  # Phase 1 fast filter on snapshot chg%
    exclude_sectors: List[str] = field(default_factory=list)
    scan_batches: List[ScannerBatch] = field(default_factory=list)


@dataclass
class WatchlistEntry:
    symbol: str
    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"


# ── Loaders ───────────────────────────────────────────────────────────────────

def _read_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_settings(path: Path) -> AppConfig:
    # Load .env from the project root (parent of the config dir) so API keys set
    # there are available via os.environ without requiring them in settings.yaml.
    load_dotenv(path.parent.parent / ".env", override=False)

    raw = _read_yaml(path)
    try:
        cfg = dacite.from_dict(AppConfig, raw, dacite.Config(strict=False))
    except dacite.DaciteError as e:
        raise ValueError(f"Invalid settings.yaml: {e}") from e
    for f in ("output_vp_poc", "output_vp_vah", "output_vp_val"):
        if getattr(cfg.ib_data, f, None) == "yfinance":
            raise ValueError(
                f"Invalid settings.yaml: {f} cannot be 'yfinance' — "
                "volume profile data is only available from IB (set to 'ibk' or null)"
            )

    # Patch API keys from environment if the yaml left them blank.
    # This lets secrets live in .env without being embedded in yaml.
    if not cfg.external_apis.finnhub_api_key:
        cfg.external_apis.finnhub_api_key = os.environ.get("FINNHUB_API_KEY", "")
    if not cfg.external_apis.fmp_api_key:
        cfg.external_apis.fmp_api_key = os.environ.get("FMP_API_KEY", "")

    return cfg


def load_screener(path: Path) -> ScreenerConfig:
    raw = _read_yaml(path)
    screener_raw = raw.get("screener", {})
    try:
        return dacite.from_dict(ScreenerConfig, screener_raw, dacite.Config(strict=False))
    except dacite.DaciteError as e:
        raise ValueError(f"Invalid screener.yaml: {e}") from e


def load_watchlist(path: Path) -> List[WatchlistEntry]:
    raw = _read_yaml(path)
    entries_raw = raw.get("watchlist", [])
    result = []
    for item in entries_raw:
        try:
            result.append(dacite.from_dict(WatchlistEntry, item, dacite.Config(strict=False)))
        except dacite.DaciteError as e:
            log.warning("Skipping invalid watchlist entry %s: %s", item, e)
    if not result:
        raise ValueError("watchlist.yaml contains no valid entries")
    return result
