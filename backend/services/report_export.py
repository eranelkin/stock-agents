from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Run, ScanResult, TickerResult
from backend.schemas.run import RunResponse, TickerResultResponse
from backend.schemas.scan import ScanResultResponse

EXPORT_FORMAT_VERSION = 2


def _log_path_for(output_dir: str) -> Path:
    """Mirrors the log-path derivation used for run deletion (runs.py)."""
    output_path = Path(output_dir)
    return output_path.parent.parent / "logs" / (output_path.name + ".html")


async def _write_run(zf: zipfile.ZipFile, run: Run, session: AsyncSession) -> None:
    """Write one run's DB rows + output files + log under `{run.id}/` in the zip."""
    prefix = f"{run.id}/"

    ticker_rows = list(
        (await session.execute(select(TickerResult).where(TickerResult.run_id == run.id)))
        .scalars()
        .all()
    )
    scan_rows = list(
        (await session.execute(select(ScanResult).where(ScanResult.run_id == run.id)))
        .scalars()
        .all()
    )

    zf.writestr(
        f"{prefix}run.json",
        json.dumps(RunResponse.model_validate(run).model_dump(mode="json")),
    )
    zf.writestr(
        f"{prefix}ticker_results.json",
        json.dumps(
            [TickerResultResponse.model_validate(t).model_dump(mode="json") for t in ticker_rows]
        ),
    )
    zf.writestr(
        f"{prefix}scan_results.json",
        json.dumps(
            [ScanResultResponse.model_validate(s).model_dump(mode="json") for s in scan_rows]
        ),
    )

    if run.output_dir:
        output_path = Path(run.output_dir)
        if output_path.is_dir():
            for f in output_path.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"{prefix}output/{f.relative_to(output_path)}")

        log_path = _log_path_for(run.output_dir)
        if log_path.is_file():
            zf.write(log_path, arcname=f"{prefix}log.html")


async def build_export_zip(runs: list[Run], session: AsyncSession) -> bytes:
    """Bundle one or more runs' DB rows + output files + logs into a single zip.

    Format (v2 — same shape for a single run or several):
      manifest.json  {format_version, exported_at, runs: [run_id, ...]}
      {run_id}/run.json
      {run_id}/ticker_results.json
      {run_id}/scan_results.json
      {run_id}/output/...   (verbatim copy of that run's output_dir)
      {run_id}/log.html     (if present)
    """
    manifest = {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "runs": [str(run.id) for run in runs],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for run in runs:
            await _write_run(zf, run, session)

    return buf.getvalue()
