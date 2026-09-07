from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    """A single orchestrator run covering all tickers in Data.json."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_names: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ticker_count: Mapped[int | None] = mapped_column(nullable=True)

    results: Mapped[list[TickerResult]] = relationship(back_populates="run")


class TickerResult(Base):
    """Aggregated pipeline output for one ticker within a run."""

    __tablename__ = "ticker_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[Run] = relationship(back_populates="results")


class AnalyticsRun(Base):
    """Tracks which completed runs have been surfaced in the Analytics tab."""

    __tablename__ = "analytics_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False, unique=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScanResult(Base):
    """Backtest simulation of a CEO recommendation against real 1-minute market data."""

    __tablename__ = "scan_results"
    __table_args__ = (UniqueConstraint("run_id", "ticker", name="uq_scan_results_run_ticker"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | no_data | error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    recommendation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    entry_low: Mapped[float | None] = mapped_column(nullable=True)
    entry_high: Mapped[float | None] = mapped_column(nullable=True)
    entry_time_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_time_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sl_low: Mapped[float | None] = mapped_column(nullable=True)
    sl_high: Mapped[float | None] = mapped_column(nullable=True)
    tp_low: Mapped[float | None] = mapped_column(nullable=True)
    tp_high: Mapped[float | None] = mapped_column(nullable=True)
    entry_window_low: Mapped[float | None] = mapped_column(nullable=True)
    entry_window_high: Mapped[float | None] = mapped_column(nullable=True)

    fill_status: Mapped[str] = mapped_column(String(20), nullable=False)  # filled | no_fill
    fill_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)  # take_profit | stop_loss | open_eod
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(nullable=True)

    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Prompt(Base):
    """A user-managed prompt, organised by category. Agents-category prompts drive the pipeline."""

    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="agents")
    search_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    search_query_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thinking_budget_tokens: Mapped[int | None] = mapped_column(nullable=True)
    search_depth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIModel(Base):
    """A configured AI model with provider details. API key stored in .env, not here."""

    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="openai_compatible")
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_env_var: Mapped[str | None] = mapped_column(String(200), nullable=True)
    search_depth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
