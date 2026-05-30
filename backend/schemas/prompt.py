from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PromptCreate(BaseModel):
    title: str
    content: str
    category: str = "agents"  # "system" | "agents" | "once" | "market"


class PromptUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None


class PromptResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    category: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
