from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunCreate(BaseModel):
    model_ids: list[uuid.UUID]
    name: str
    tickers: list[dict[str, Any]]


class RunResponse(BaseModel):
    id: uuid.UUID
    status: str
    name: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    output_dir: str | None = None

    model_config = {"from_attributes": True}
