from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AnalyticsRun, Run
from backend.db.session import get_session
from backend.schemas.run import RunResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=list[RunResponse])
async def list_analytics(session: AsyncSession = Depends(get_session)) -> list[Run]:
    """Sync newly completed runs into analytics_runs, then return the tracked list."""
    tracked = select(AnalyticsRun.run_id)
    result = await session.execute(
        select(Run.id).where(Run.status == "completed", Run.id.notin_(tracked))
    )
    new_ids = [row[0] for row in result.all()]
    for run_id in new_ids:
        session.add(AnalyticsRun(run_id=run_id))
    if new_ids:
        await session.commit()

    result = await session.execute(
        select(Run)
        .join(AnalyticsRun, AnalyticsRun.run_id == Run.id)
        .order_by(Run.created_at.desc())
    )
    return list(result.scalars().all())
