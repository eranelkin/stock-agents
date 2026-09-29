from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Run, ScanResult, TickerResult
from backend.services.report_export import EXPORT_FORMAT_VERSION


def _row_kwargs(model: type, row: dict[str, Any], exclude: set[str]) -> dict[str, Any]:
    """Intersect an exported JSON row with `model`'s actual columns, coercing
    ISO datetime strings back to `datetime` for DateTime columns. Driven by
    the model's columns (not a hardcoded field list) so it stays correct as
    ScanResult/TickerResult grow new fields over time."""
    kwargs: dict[str, Any] = {}
    for col in model.__table__.columns:
        name = col.name
        if name in exclude or name not in row:
            continue
        value = row[name]
        if value is not None and isinstance(col.type, DateTime):
            value = datetime.fromisoformat(value)
        kwargs[name] = value
    return kwargs


async def _import_one_run(
    zf: zipfile.ZipFile, run_id: str, names: set[str], session: AsyncSession
) -> Run:
    """Import a single `{run_id}/...` folder from the zip, minting a fresh
    run_id and output-dir timestamp — never reuses the original ID/timestamp,
    so this can never collide with anything already on the target machine.
    `created_at`/`completed_at` are preserved, since Analytics ties
    trading-day lookups to the run's original creation time.
    """
    prefix = f"{run_id}/"
    for required in ("run.json", "ticker_results.json", "scan_results.json"):
        if prefix + required not in names:
            raise ValueError(f"Malformed export bundle: missing {prefix}{required}")

    run_data = json.loads(zf.read(prefix + "run.json"))
    ticker_rows = json.loads(zf.read(prefix + "ticker_results.json"))
    scan_rows = json.loads(zf.read(prefix + "scan_results.json"))

    new_run_id = uuid.uuid4()
    # Suffix with a slice of the new run_id, not just a timestamp — a bulk
    # import restores several runs within the same wall-clock second, and a
    # bare timestamp would collide, silently overwriting one run's output
    # files with another's.
    new_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S") + f"_{new_run_id.hex[:8]}"
    new_output_dir = f"outputs/runs/{new_ts}"

    run_kwargs = _row_kwargs(
        Run, run_data, exclude={"id", "output_dir", "ibk_session_id", "is_favorite"}
    )
    run = Run(
        id=new_run_id,
        output_dir=new_output_dir,
        ibk_session_id=None,  # tied to the exporting machine's IBK session; meaningless here
        is_favorite=False,
        **run_kwargs,
    )
    session.add(run)

    for row in ticker_rows:
        kwargs = _row_kwargs(TickerResult, row, exclude={"id", "run_id"})
        session.add(TickerResult(id=uuid.uuid4(), run_id=new_run_id, **kwargs))

    for row in scan_rows:
        kwargs = _row_kwargs(ScanResult, row, exclude={"id", "run_id", "scanned_at"})
        session.add(ScanResult(id=uuid.uuid4(), run_id=new_run_id, **kwargs))

    # Extract files before committing DB rows, so a filesystem failure here
    # doesn't leave an orphaned DB row behind.
    output_path = Path(new_output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_prefix = f"{prefix}output/"
    for member in names:
        if member.startswith(output_prefix) and not member.endswith("/"):
            target = output_path / member[len(output_prefix) :]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))

    log_member = f"{prefix}log.html"
    if log_member in names:
        log_path = Path("outputs/logs") / f"{new_ts}.html"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_bytes(zf.read(log_member))

    return run


async def import_run_zip(data: bytes, session: AsyncSession) -> list[Run]:
    """Import a bundle produced by `report_export.build_export_zip` — one or
    more runs, each restored with a fresh run_id/output-dir. All runs in the
    bundle are imported in one DB transaction (all-or-nothing)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Not a valid zip file") from exc

    names = set(zf.namelist())
    if "manifest.json" not in names:
        raise ValueError("Malformed export bundle: missing manifest.json")

    manifest = json.loads(zf.read("manifest.json"))
    if manifest.get("format_version") != EXPORT_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported export format_version {manifest.get('format_version')!r} "
            f"(this backend supports {EXPORT_FORMAT_VERSION})"
        )

    run_ids = manifest.get("runs") or []
    if not run_ids:
        raise ValueError("Malformed export bundle: manifest lists no runs")

    imported = [await _import_one_run(zf, run_id, names, session) for run_id in run_ids]

    await session.commit()
    for run in imported:
        await session.refresh(run)
    return imported
