from __future__ import annotations

import httpx

from ai_service.config import settings
from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


async def notify_run_alert(run_id: str, message: str) -> None:
    """Best-effort notice to the backend that this run hit something worth a popup.

    Fire-and-forget: never raises, and a failure here never affects the run —
    it just means the user doesn't see the popup.
    """
    if not run_id:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.backend_url}/runs/{run_id}/alert",
                json={"message": message},
            )
    except Exception as exc:
        logger.warning("Failed to notify backend of run alert: %s", exc, extra={"run_id": run_id})
