from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from ib_async import BarData, Contract

from src.config.loader import AppConfig # Added for conditional record building
from src.ib.contract_details import ContractInfo
from src.ib.market_data import MarketSnapshot
from src.processing.atr import calculate_atr

log = logging.getLogger(__name__)


# ── Indicator helpers ──────────────────────────────────────────────────────────

def _compute_ema(bars: list, period: int) -> Optional[float]:
    closes = [b.close for b in bars if b.close is not None]
    if len(closes) < period + 1:
        return None
    ema = sum(closes[:period]) / period
    k = 2 / (period + 1)
    for c in closes[period:]:
        ema = c * k + ema * (1 - k)
    return round(ema, 4)


def _compute_rsi(bars: list, period: int = 14) -> Optional[float]:
    closes = [b.close for b in bars if b.close is not None]
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [max(d, 0)      for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]
    avg_gain = sum(gains[:period])  / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _compute_beta(stock_bars: List[BarData], benchmark_bars: List[BarData]) -> Optional[float]:
    """Calculate beta from stock and benchmark daily bars."""
    if not stock_bars or not benchmark_bars:
        return None

    # Align bars by timestamp
    stock_prices = {b.date: b.close for b in stock_bars}
    bench_prices = {b.date: b.close for b in benchmark_bars}
    
    common_dates = sorted(list(set(stock_prices.keys()) & set(bench_prices.keys())))
    
    if len(common_dates) < 2:
        return None
        
    stock_series = np.array([stock_prices[d] for d in common_dates])
    bench_series = np.array([bench_prices[d] for d in common_dates])
    
    # Calculate returns
    stock_returns = np.diff(stock_series) / stock_series[:-1]
    bench_returns = np.diff(bench_series) / bench_series[:-1]
    
    if len(stock_returns) < 2:
        return None

    # Calculate covariance and variance
    covariance_matrix = np.cov(stock_returns, bench_returns)
    if covariance_matrix.shape != (2, 2):
        return None
        
    covariance = covariance_matrix[0, 1]
    variance = np.var(bench_returns)

    if variance == 0:
        return None
        
    beta = covariance / variance
    return round(beta, 3)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class StockRecord:
    # ── Core identity ──────────────────────────────────────────────────────────
    symbol: str
    company_name: str
    sector: str
    contract: Contract

    # ── Raw numeric values (used for filtering and sorting) ────────────────────
    market_cap_usd: Optional[float]
    pre_market_price: Optional[float]
    pre_market_volume: Optional[float]
    pre_market_chg_pct: Optional[float]
    price: Optional[float]   # previous regular-session close
    atr: Optional[float]     # Wilder ATR-14 as % of close

    # ── New fields added in Phase 1 (derived from existing data) ──────────────
    industry: str = ""
    prev_chg_pct: Optional[float] = None
    prev_day_high: Optional[float] = None
    prev_day_low: Optional[float] = None
    prev_day_open: Optional[float] = None
    avg_daily_volume_20d: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    shares_outstanding: Optional[float] = None
    beta: Optional[float] = None
    emas: Dict[int, Optional[float]] = field(default_factory=dict)
    rsi_14: Optional[float] = None
    mc_vol_ratio: Optional[float] = None

    # ── Populated by pre-market 1-min bar fetcher (Phase 2) ───────────────────
    pre_market_high: Optional[float] = None
    pre_market_low: Optional[float] = None
    rvol_pre_market: Optional[float] = None

    # ── Populated by previous-session VWAP fetcher (Phase 3) ─────────────────
    vwap_prev_session: Optional[float] = None

    # ── Populated by benchmark fetcher (Phase 4) ──────────────────────────────
    benchmark_symbol: str = ""
    benchmark_prev_close: Optional[float] = None
    benchmark_pre_market_price: Optional[float] = None
    benchmark_pre_market_chg_pct: Optional[float] = None

    # ── Populated by volume profile fetcher (Phase 6) ─────────────────────────
    vp_poc: Optional[float] = None
    vp_vah: Optional[float] = None
    vp_val: Optional[float] = None
    vp_lookback_sessions: Optional[int] = None

    # ── Populated by external HTTP enrichment (Phase 7) ───────────────────────
    float_pct: Optional[float] = None
    next_earnings_date: Optional[str] = None
    news_catalysts: list = field(default_factory=list)
    short_float_pct: Optional[float] = None
    short_ratio: Optional[float] = None
    institutional_holding_pct: Optional[float] = None


# ── Builder ────────────────────────────────────────────────────────────────────

def build_single_record(
    symbol: str,
    info: ContractInfo,
    snap: MarketSnapshot | None,
    bars: List[BarData],
    app_config: AppConfig | None = None,
    atr_val: float | None = None,
    atr_period: int = 14,
    ema_periods: List[int] | None = None,
    rsi_period: int = 14,
) -> StockRecord:
    """Build one StockRecord from a single symbol's data.

    atr_val: pre-computed ATR (skips recalculation when provided).
    """
    if ema_periods is None:
        ema_periods = [9, 20, 50, 200]

    ib_data_cfg = app_config.ib_data if app_config else None

    if atr_val is None and (ib_data_cfg is None or ib_data_cfg.output_atr == "ibk"):
        atr_val = calculate_atr(bars, atr_period) if bars else None

    prev_day_high_val = None
    if ib_data_cfg is None or ib_data_cfg.output_prev_day_high == "ibk":
        prev_day_high_val = bars[-2].high if len(bars) >= 2 else None

    prev_day_low_val = None
    if ib_data_cfg is None or ib_data_cfg.output_prev_day_low == "ibk":
        prev_day_low_val = bars[-2].low if len(bars) >= 2 else None

    prev_day_open_val = None
    if ib_data_cfg is None or ib_data_cfg.output_prev_day_open == "ibk":
        prev_day_open_val = bars[-2].open if len(bars) >= 2 else None

    avg_daily_volume_20d_val = None
    if ib_data_cfg is None or ib_data_cfg.output_avg_daily_volume_20d == "ibk":
        avg_daily_volume_20d_val = (
            sum(b.volume for b in bars) / len(bars) if bars else None
        )

    emas_val: Dict[int, Optional[float]] = {}
    if (ib_data_cfg is None or ib_data_cfg.output_ema == "ibk") and ema_periods:
        for period in ema_periods:
            emas_val[period] = _compute_ema(bars, period)

    rsi_14_val = None
    if ib_data_cfg is None or ib_data_cfg.output_rsi == "ibk":
        rsi_14_val = _compute_rsi(bars, rsi_period)

    return StockRecord(
        symbol=symbol,
        contract=info.contract,
        company_name=info.company_name if (ib_data_cfg is None or ib_data_cfg.output_company_name == "ibk") else None,
        sector=info.sector if (ib_data_cfg is None or ib_data_cfg.output_sector == "ibk") else None,
        market_cap_usd=(snap.market_cap_usd if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_market_cap == "ibk") else None,
        pre_market_price=(snap.pre_market_price if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_pre_market_price == "ibk") else None,
        pre_market_volume=(snap.pre_market_volume if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_pre_market_volume in ("ibk", "finnhub", "yfinance")) else None,
        pre_market_chg_pct=(snap.pre_market_chg_pct if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_pre_market_chg_pct == "ibk") else None,
        price=(snap.prev_close if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_prev_close == "ibk") else None,
        atr=atr_val,
        industry=info.industry if (ib_data_cfg is None or ib_data_cfg.output_industry == "ibk") else None,
        prev_day_high=prev_day_high_val,
        prev_day_low=prev_day_low_val,
        prev_day_open=prev_day_open_val,
        avg_daily_volume_20d=avg_daily_volume_20d_val,
        fifty_two_week_high=(snap.fifty_two_week_high if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_fifty_two_week_high == "ibk") else None,
        fifty_two_week_low=(snap.fifty_two_week_low if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_fifty_two_week_low == "ibk") else None,
        shares_outstanding=(snap.shares_outstanding if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_shares_outstanding == "ibk") else None,
        beta=(snap.beta if snap else None) if (ib_data_cfg is None or ib_data_cfg.output_beta == "ibk") else None,
        emas=emas_val,
        rsi_14=rsi_14_val,
        mc_vol_ratio=None,
    )


def build_records(
    contract_infos: Dict[str, ContractInfo],
    snapshots: Dict[str, MarketSnapshot],
    bars_map: Dict[str, List[BarData]],
    app_config: AppConfig | None = None,
    atr_map: Dict[str, float | None] | None = None,
    atr_period: int = 14,
    ema_periods: List[int] | None = None,
    rsi_period: int = 14,
) -> List[StockRecord]:
    """Assemble a StockRecord for every symbol that has contract details."""
    if ema_periods is None:
        ema_periods = [9, 20, 50, 200]
    records = [
        build_single_record(
            symbol=sym,
            info=info,
            snap=snapshots.get(sym),
            bars=bars_map.get(sym, []),
            app_config=app_config,
            atr_val=(atr_map.get(sym) if atr_map is not None else None),
            atr_period=atr_period,
            ema_periods=ema_periods,
            rsi_period=rsi_period,
        )
        for sym, info in contract_infos.items()
    ]
    log.info("Built %d stock records", len(records))
    return records
