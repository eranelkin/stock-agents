from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AgentMetadata(BaseModel):
    pipeline_duration_ms: int
    agent_count: int
    timestamp: str


class PipelineOutput(BaseModel):
    """Aggregated result for one ticker across all agents."""

    ticker: str
    model_name: str
    agents: dict[str, Any]
    metadata: AgentMetadata
