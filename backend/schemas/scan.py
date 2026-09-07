from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScanResultResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    ticker: str

    status: str
    error_message: str | None = None

    recommendation: dict[str, Any]
    entry_low: float | None = None
    entry_high: float | None = None
    entry_time_start: str | None = None
    entry_time_end: str | None = None
    sl_low: float | None = None
    sl_high: float | None = None
    tp_low: float | None = None
    tp_high: float | None = None
    entry_window_low: float | None = None
    entry_window_high: float | None = None

    fill_status: str
    fill_time: datetime | None = None
    fill_price: float | None = None
    exit_reason: str | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    pnl_pct: float | None = None
    r_multiple: float | None = None

    scanned_at: datetime

    model_config = {"from_attributes": True}
