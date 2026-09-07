from __future__ import annotations

import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AnalyticsRun, Run, ScanResult
from backend.db.session import get_session
from backend.schemas.run import RunResponse
from backend.schemas.scan import ScanResultResponse
from backend.services.ceo_parser import parse_ceo_file
from backend.services.market_data import fetch_1m_candles
from backend.services.trade_simulator import normalize_recommendation, simulate_trade

router = APIRouter(prefix="/analytics", tags=["analytics"])

ET = ZoneInfo("America/New_York")


@router.get("", response_model=list[RunResponse])
async def list_analytics(session: AsyncSession = Depends(get_session)) -> list[Run]:
    """Sync newly completed runs into analytics_runs, then return the tracked list."""
    tracked = select(AnalyticsRun.run_id)
    result = await session.execute(
        select(Run.id).where(Run.status == "completed", Run.id.notin_(tracked))
    )
    new_ids = [row[0] for row in result.all()]
    for run_id in new_ids:
        session.add(AnalyticsRun(run_id=run_id))
    if new_ids:
        await session.commit()

    result = await session.execute(
        select(Run)
        .join(AnalyticsRun, AnalyticsRun.run_id == Run.id)
        .order_by(Run.created_at.desc())
    )
    runs = list(result.scalars().all())

    scan_times = await session.execute(
        select(ScanResult.run_id, func.max(ScanResult.scanned_at)).group_by(ScanResult.run_id)
    )
    last_scanned_by_run = dict(scan_times.all())
    for run in runs:
        run.last_scanned_at = last_scanned_by_run.get(run.id)  # type: ignore[attr-defined]

    return runs


@router.post("/{run_id}/scan", response_model=list[ScanResultResponse])
async def scan_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ScanResult]:
    """Simulate every ticker's CEO recommendation for a completed run against real
    1-minute market data, upserting one ScanResult row per ticker."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "completed":
        raise HTTPException(status_code=409, detail="Run has not completed successfully")
    if not run.output_dir:
        raise HTTPException(status_code=409, detail="Run has no output directory")

    trading_date = run.created_at.astimezone(ET).date()

    ceo_files: dict[str, Path] = {}
    for ext in ("yaml", "json"):
        for f in sorted(Path(run.output_dir).glob(f"CEO_*.{ext}")):
            ceo_files.setdefault(f.stem[4:], f)

    for ticker, path in ceo_files.items():
        raw = parse_ceo_file(path)
        rec = normalize_recommendation(raw) if raw else None

        await session.execute(
            sql_delete(ScanResult).where(
                ScanResult.run_id == run_id, ScanResult.ticker == ticker
            )
        )

        if rec is None:
            session.add(
                ScanResult(
                    run_id=run_id,
                    ticker=ticker,
                    status="error",
                    error_message="Could not parse recommendation",
                    recommendation=raw or {},
                    fill_status="no_fill",
                )
            )
            continue

        candles = await fetch_1m_candles(ticker, trading_date)
        if candles is None:
            session.add(
                ScanResult(
                    run_id=run_id,
                    ticker=ticker,
                    status="no_data",
                    error_message=(
                        "Market data unavailable for this date — either Yahoo Finance "
                        "has no 1-minute history that far back (~7 days max), or the "
                        "request timed out/was rate-limited. Try again later."
                    ),
                    recommendation=raw,
                    entry_low=rec.entry_low,
                    entry_high=rec.entry_high,
                    entry_time_start=rec.entry_time_start.isoformat(timespec="minutes"),
                    entry_time_end=rec.entry_time_end.isoformat(timespec="minutes"),
                    sl_low=rec.sl_low,
                    sl_high=rec.sl_high,
                    tp_low=rec.tp_low,
                    tp_high=rec.tp_high,
                    fill_status="no_fill",
                )
            )
            continue

        outcome = simulate_trade(rec, candles)
        session.add(
            ScanResult(
                run_id=run_id,
                ticker=ticker,
                status="completed",
                recommendation=raw,
                entry_low=rec.entry_low,
                entry_high=rec.entry_high,
                entry_time_start=rec.entry_time_start.isoformat(timespec="minutes"),
                entry_time_end=rec.entry_time_end.isoformat(timespec="minutes"),
                sl_low=rec.sl_low,
                sl_high=rec.sl_high,
                tp_low=rec.tp_low,
                tp_high=rec.tp_high,
                entry_window_low=outcome.entry_window_low,
                entry_window_high=outcome.entry_window_high,
                fill_status=outcome.fill_status,
                fill_time=outcome.fill_time,
                fill_price=outcome.fill_price,
                exit_reason=outcome.exit_reason,
                exit_time=outcome.exit_time,
                exit_price=outcome.exit_price,
                pnl_pct=outcome.pnl_pct,
                r_multiple=outcome.r_multiple,
            )
        )

    await session.commit()

    result = await session.execute(select(ScanResult).where(ScanResult.run_id == run_id))
    return list(result.scalars().all())


@router.get("/{run_id}/scan", response_model=list[ScanResultResponse])
async def get_scan_results(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[ScanResult]:
    """Return previously computed scan results without recomputing."""
    result = await session.execute(select(ScanResult).where(ScanResult.run_id == run_id))
    return list(result.scalars().all())
