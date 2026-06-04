from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from backend.db.models import Run
from backend.schemas.run import RunResponse


class RunBroadcaster:
    """Fans out run-list updates to all connected SSE clients.

    A single background task polls the DB every second. When the serialised
    run list changes it pushes the new payload to every subscribed queue.
    This keeps DB load constant regardless of how many browser tabs are open.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._last_payload: str = ""

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    def broadcast(self, payload: str) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow client: drop update; next poll delivers current state

    async def start(self, session_factory) -> None:
        """Background loop: poll DB every 1 s, broadcast on state change."""
        while True:
            try:
                async with session_factory() as session:
                    result = await session.execute(
                        select(Run).order_by(Run.created_at.desc())
                    )
                    runs = result.scalars().all()
                payload = json.dumps(
                    [RunResponse.model_validate(r).model_dump(mode="json") for r in runs],
                    default=str,
                )
                if payload != self._last_payload:
                    self._last_payload = payload
                    self.broadcast(payload)
            except Exception:
                pass  # never crash the background task
            await asyncio.sleep(1.0)


broadcaster = RunBroadcaster()
