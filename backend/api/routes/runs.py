from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

import aiofiles
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.broadcaster import broadcaster
from backend.config import settings
from backend.db.models import AIModel, Prompt, Run, TickerResult
from backend.db.session import AsyncSessionLocal, get_session
from backend.schemas.run import RunCreate, RunResponse

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreate, session: AsyncSession = Depends(get_session)
) -> Run:
    """Create a Run record and trigger the AI service to begin processing."""
    if not body.tickers:
        raise HTTPException(status_code=400, detail="Tickers list is empty.")

    result = await session.execute(
        select(AIModel).where(
            AIModel.id.in_(body.model_ids),
            AIModel.is_active == True,  # noqa: E712
        )
    )
    ai_models = result.scalars().all()

    if not ai_models:
        raise HTTPException(
            status_code=400,
            detail="No active models found for the provided IDs. Enable models in the Models tab first.",
        )

    prompt_result = await session.execute(
        select(Prompt).where(Prompt.category == "agents", Prompt.is_active == True)  # noqa: E712
    )
    agent_prompts = prompt_result.scalars().all()
    if not agent_prompts:
        raise HTTPException(
            status_code=400,
            detail="No active Agent prompts configured. Enable prompts in the Agents tab first.",
        )

    sector_prompt_result = await session.execute(
        select(Prompt).where(Prompt.category == "sectors", Prompt.is_active == True)  # noqa: E712
    )
    sector_prompts = sector_prompt_result.scalars().all()

    ceo_prompt_result = await session.execute(
        select(Prompt).where(Prompt.category == "ceo", Prompt.is_active == True)  # noqa: E712
    )
    ceo_prompts = ceo_prompt_result.scalars().all()

    model_configs = [
        {
            "id": str(m.id),
            "name": m.name,
            "model_id": m.model_id,
            "base_url": m.base_url,
            "api_key": os.environ.get(m.api_key_env_var) if m.api_key_env_var else None,
        }
        for m in ai_models
    ]

    run = Run(name=body.name)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.ai_service_url}/run",
                json={
                    "run_id": str(run.id),
                    "models": model_configs,
                    "tickers": body.tickers,
                    "prompts": [
                        {
                            "id": str(p.id),
                            "title": p.title,
                            "content": p.content,
                            "search_enabled": p.search_enabled,
                            "search_query_template": p.search_query_template,
                            "search_mode": p.search_mode,
                        }
                        for p in agent_prompts
                    ],
                    "sector_prompts": [
                        {
                            "id": str(p.id),
                            "title": p.title,
                            "content": p.content,
                            "search_enabled": p.search_enabled,
                            "search_query_template": p.search_query_template,
                            "search_mode": p.search_mode,
                        }
                        for p in sector_prompts
                    ],
                    "ceo_prompts": [
                        {
                            "id": str(p.id),
                            "title": p.title,
                            "content": p.content,
                            "search_enabled": p.search_enabled,
                            "search_query_template": p.search_query_template,
                            "search_mode": p.search_mode,
                        }
                        for p in ceo_prompts
                    ],
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            run.status = "failed"
            run.error = f"Could not reach ai-service: {exc}"
            await session.commit()
            raise HTTPException(status_code=502, detail="Failed to reach ai-service") from exc

    return run


@router.get("", response_model=list[RunResponse])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[Run]:
    """Return all runs ordered by creation time descending."""
    result = await session.execute(select(Run).order_by(Run.created_at.desc()))
    return list(result.scalars().all())


@router.get("/stream")
async def stream_runs() -> StreamingResponse:
    """SSE: pushes the full run list to the client whenever state changes."""
    async def generator() -> AsyncGenerator[str, None]:
        q = broadcaster.subscribe()
        try:
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Run).order_by(Run.created_at.desc()))
                    runs = result.scalars().all()
                payload = json.dumps(
                    [RunResponse.model_validate(r).model_dump(mode="json") for r in runs],
                    default=str,
                )
                yield f"data: {payload}\n\n"
            except Exception:
                yield "data: []\n\n"  # DB unavailable; broadcaster will push real data once it connects
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    return
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Run:
    """Return a single run by ID."""
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/stop", response_model=RunResponse)
async def stop_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Run:
    """Cancel an active run. No-op (409) if the run is not pending or running."""
    from datetime import datetime, timezone

    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Run is already in terminal state: {run.status}",
        )

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.ai_service_url}/stop/{run_id}",
                timeout=5.0,
            )
        except httpx.HTTPError:
            pass  # best-effort; proceed to mark cancelled in DB regardless

    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(run)
    return run


@router.delete("/{run_id}", status_code=204, response_class=Response)
async def delete_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Delete a run, its ticker results, and its output directory if it exists.

    If the run is active, cancels it in the AI service first.
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in ("pending", "running"):
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{settings.ai_service_url}/stop/{run_id}",
                    timeout=5.0,
                )
            except httpx.HTTPError:
                pass  # best-effort; deletion proceeds regardless

    output_dir = run.output_dir

    await session.execute(sql_delete(TickerResult).where(TickerResult.run_id == run_id))
    await session.delete(run)
    await session.commit()

    if output_dir:
        output_path = Path(output_dir)
        if output_path.exists() and output_path.is_dir():
            shutil.rmtree(output_path)
        # Log file lives at <base>/logs/<timestamp>.html, parallel to <base>/runs/<timestamp>
        log_path = output_path.parent.parent / "logs" / (output_path.name + ".html")
        if log_path.exists():
            log_path.unlink()

    return Response(status_code=204)


@router.get("/{run_id}/log", response_class=HTMLResponse)
async def get_run_log(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Serve the HTML log file for a run.

    Injects window.__INITIAL_BYTES__ so the embedded polling JS starts fetching
    only new content appended after this page load.
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output_dir:
        raise HTTPException(status_code=404, detail="Log not yet available — run has not started")

    log_path = _log_file_path(run.output_dir)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not yet written")

    content = log_path.read_text(encoding="utf-8")
    file_size = log_path.stat().st_size
    injection = f"<script>window.__INITIAL_BYTES__={file_size};</script>"

    if "</body>" in content:
        content = content.replace("</body>", injection + "</body>", 1)
    else:
        content += injection

    return HTMLResponse(content=content)


@router.get("/{run_id}/log-rows")
async def get_log_rows(
    run_id: uuid.UUID,
    since_bytes: int = 0,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return new HTML rows appended to the log file since the given byte offset.

    Used by the embedded polling JS to fetch and append live event rows without
    a full page reload.
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.output_dir:
        return {"html": "", "next_bytes": 0, "done": False, "stats": {}}

    log_path = _log_file_path(run.output_dir)
    if not log_path.exists():
        return {"html": "", "next_bytes": 0, "done": False, "stats": {}}

    file_size = log_path.stat().st_size
    new_html = ""
    if file_size > since_bytes:
        async with aiofiles.open(log_path, "rb") as f:
            await f.seek(since_bytes)
            raw = await f.read()
        new_html = raw.decode("utf-8", errors="replace")

    done = run.status in ("completed", "failed")
    stats = _parse_log_stats(new_html) if new_html else {}

    return {"html": new_html, "next_bytes": file_size, "done": done, "stats": stats}


@router.get("/{run_id}/log-stream")
async def stream_run_log(
    run_id: uuid.UUID,
    since_bytes: int = 0,
) -> StreamingResponse:
    """SSE: streams new log rows for a run as they are appended to the log file."""
    async def generator() -> AsyncGenerator[str, None]:
        offset = since_bytes
        idle_ticks = 0  # half-second ticks since last data frame
        while True:
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                return
            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
            if run is None:
                yield "event: done\ndata: {}\n\n"
                await asyncio.sleep(10)
                break

            sent_data = False
            if run.output_dir:
                log_path = _log_file_path(run.output_dir)
                if log_path.exists():
                    file_size = log_path.stat().st_size
                    if file_size > offset:
                        async with aiofiles.open(log_path, "rb") as f:
                            await f.seek(offset)
                            raw = await f.read()
                        new_html = raw.decode("utf-8", errors="replace")
                        offset = file_size
                        payload = json.dumps(
                            {"html": new_html, "stats": _parse_log_stats(new_html)}
                        )
                        yield f"data: {payload}\n\n"
                        sent_data = True

            if sent_data:
                idle_ticks = 0
            else:
                idle_ticks += 1
                if idle_ticks >= 30:  # keepalive every ~15 s
                    yield ": keepalive\n\n"
                    idle_ticks = 0

            if run.status in ("completed", "failed", "cancelled"):
                yield "event: done\ndata: {}\n\n"
                # Keep the connection open briefly so the client can receive and
                # process the 'done' event and call es.close() before the server
                # closes the socket. Without this, EventSource reconnects in a loop.
                await asyncio.sleep(10)
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{run_id}/ceo-stream")
async def stream_ceo_results(run_id: uuid.UUID) -> StreamingResponse:
    """SSE: streams CEO analysis rows as CEO_*.yaml files land on disk."""
    async def generator() -> AsyncGenerator[str, None]:
        seen: set[str] = set()

        async with AsyncSessionLocal() as session:
            run = await session.get(Run, run_id)
        if run is None:
            yield "event: done\ndata: {}\n\n"
            return

        if run.output_dir:
            for f in sorted(Path(run.output_dir).glob("CEO_*.yaml")):
                ticker = f.stem[4:]
                data = _parse_ceo_yaml(f)
                if data:
                    seen.add(ticker)
                    yield f"data: {json.dumps({'ticker': ticker, 'data': data})}\n\n"

        if run.status in ("completed", "failed", "cancelled"):
            yield "event: done\ndata: {}\n\n"
            return

        idle_ticks = 0
        while True:
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return

            async with AsyncSessionLocal() as session:
                run = await session.get(Run, run_id)
            if run is None:
                yield "event: done\ndata: {}\n\n"
                break

            if run.output_dir:
                for f in sorted(Path(run.output_dir).glob("CEO_*.yaml")):
                    ticker = f.stem[4:]
                    if ticker not in seen:
                        data = _parse_ceo_yaml(f)
                        if data:
                            seen.add(ticker)
                            yield f"data: {json.dumps({'ticker': ticker, 'data': data})}\n\n"
                            idle_ticks = 0

            idle_ticks += 1
            if idle_ticks >= 15:
                yield ": keepalive\n\n"
                idle_ticks = 0

            if run.status in ("completed", "failed", "cancelled"):
                yield "event: done\ndata: {}\n\n"
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _log_file_path(output_dir: str) -> Path:
    """Derive the HTML log file path from a run's output_dir."""
    ts = Path(output_dir).name  # e.g. "2026-06-04_10-00-00"
    return Path(output_dir).parent.parent / "logs" / f"{ts}.html"


def _parse_ceo_yaml(file_path: Path) -> dict | None:
    """Extract the stock analysis dict from a CEO_*.yaml output file.

    Handles two LLM output patterns:
    - Each analysis field as a separate list item under `stocks`
    - Analysis fields as siblings of `stocks` at the agent level
    Both are merged into one flat dict.
    """
    import yaml
    try:
        with open(file_path) as f:
            doc = yaml.safe_load(f)
        for agent_data in doc.get("agents", {}).values():
            if not isinstance(agent_data, dict):
                continue
            merged: dict = {}
            # Merge all items in the stocks list (handles LLM pattern where each
            # field is its own list entry: [{symbol: X}, {confidence: 72}, ...])
            for item in agent_data.get("stocks") or []:
                if isinstance(item, dict):
                    merged.update(item)
            # Also pull in analysis fields sitting directly on agent_data
            # (LLM sometimes places them outside the stocks list)
            _SKIP = {"stocks", "raw_output", "parse_error", "reasoning"}
            for k, v in agent_data.items():
                if k in _SKIP:
                    continue
                if isinstance(k, str) and len(k) < 100:
                    merged.setdefault(k, v)
            if merged:
                return merged
    except Exception:
        pass
    return None


def _parse_log_stats(html: str) -> dict[str, int]:
    """Count delta stats from a chunk of newly-read log HTML."""
    return {
        "llm":  len(re.findall(r'class="event-row type-llm-req"', html)),
        "ok":   len(re.findall(r'class="event-row type-llm-ok"', html)),
        "err":  len(re.findall(r'class="event-row type-llm-err"', html)),
        "ptok": sum(int(m) for m in re.findall(r'data-prompt-tok="(\d+)"', html)),
        "ctok": sum(int(m) for m in re.findall(r'data-comp-tok="(\d+)"', html)),
        "ttok": sum(int(m) for m in re.findall(r'data-total-tok="(\d+)"', html)),
    }
