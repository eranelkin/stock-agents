from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class RunCreate(BaseModel):
    model_ids: list[uuid.UUID]
    name: str
    tickers: list[dict[str, Any]]
    direction: str = "long"  # "long" | "short"
    env: Literal["prod", "test"] = "test"


class BulkDeleteRequest(BaseModel):
    run_ids: list[uuid.UUID]


class RunAlertRequest(BaseModel):
    message: str


class RunResponse(BaseModel):
    id: uuid.UUID
    status: str
    name: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    alert: str | None = None
    output_dir: str | None = None
    model_names: list[str] | None = None
    ticker_count: int | None = None
    ibk_session_id: str | None = None
    is_favorite: bool = False
    direction: str = "long"
    env: str = "test"

    model_config = {"from_attributes": True}
