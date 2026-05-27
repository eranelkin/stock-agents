from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RunResponse(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}
