from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PromptCreate(BaseModel):
    title: str
    content: str
    category: str = "agents"  # "agents" | "ceo" | "sectors" | "system" | "once" | "market"
    search_enabled: bool = False
    search_query_template: str | None = None
    search_mode: str | None = None  # None = use global; "prefetch" | "tool_call"
    is_active: bool = True


class PromptUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    search_enabled: bool | None = None
    search_query_template: str | None = None
    search_mode: str | None = None
    is_active: bool | None = None


class PromptActiveUpdate(BaseModel):
    is_active: bool


class PromptResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    category: str
    search_enabled: bool
    search_query_template: str | None
    search_mode: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
