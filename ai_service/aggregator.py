from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_service.schemas.output import AgentMetadata, PipelineOutput


class Aggregator:
    """Merges per-agent results for one ticker into a single PipelineOutput."""

    def aggregate(
        self,
        ticker: str,
        agent_results: dict[str, Any],
        duration_ms: int,
    ) -> PipelineOutput:
        """Build a PipelineOutput from collected agent results.

        Args:
            ticker: The stock ticker symbol.
            agent_results: Mapping of prompt_id → agent output dict.
            duration_ms: Total pipeline wall-clock time in milliseconds.

        Returns:
            A validated PipelineOutput instance.
        """
        return PipelineOutput(
            ticker=ticker,
            agents=agent_results,
            metadata=AgentMetadata(
                pipeline_duration_ms=duration_ms,
                agent_count=len(agent_results),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )
