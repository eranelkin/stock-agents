from __future__ import annotations

from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Model configuration passed from backend to ai-service per run."""

    id: str
    name: str
    model_id: str  # full litellm model string e.g. "groq/llama-3.3-70b-versatile"
    base_url: str | None = None
    api_key: str | None = None


class PromptConfig(BaseModel):
    """Prompt configuration passed from backend to ai-service per run."""

    id: str
    title: str
    content: str
