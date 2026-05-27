from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TickerResultResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    ticker: str
    output: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
