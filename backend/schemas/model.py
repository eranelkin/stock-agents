from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ModelCreate(BaseModel):
    name: str
    model_id: str
    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key: str | None = None
    search_depth: str | None = None  # "basic" | "advanced" | None = use global default


class ModelUpdate(BaseModel):
    name: str | None = None
    model_id: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # empty string = keep existing; new value = update
    search_depth: str | None = None


class ModelActiveUpdate(BaseModel):
    is_active: bool


class ModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_id: str
    provider: str
    base_url: str | None
    api_key_configured: bool
    search_depth: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
