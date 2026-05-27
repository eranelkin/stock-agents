from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TickerResult
from backend.db.session import get_session
from backend.schemas.result import TickerResultResponse

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{run_id}", response_model=list[TickerResultResponse])
async def get_results(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[TickerResult]:
    """Return all ticker results for a given run."""
    result = await session.execute(
        select(TickerResult).where(TickerResult.run_id == run_id)
    )
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=404, detail="No results found for this run")
    return rows
