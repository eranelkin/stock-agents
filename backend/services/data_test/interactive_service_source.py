from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.services.data_test.field_registry import resolve_ibk_path_list

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]


class InteractiveServiceError(Exception):
    """Raised when the interactive-service subprocess fails or times out."""


async def _run_adhoc(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Spawn interactive-service's CLI in ad hoc mode and return {symbol: raw_record}.

    Never called with an empty symbol list. Raises InteractiveServiceError on any
    failure (IB Gateway not running, timeout, bad output) — callers must catch it
    and degrade gracefully rather than letting one source kill the whole comparison.
    """
    service_dir = Path(settings.interactive_service_dir)
    if not service_dir.is_absolute():
        service_dir = _REPO_ROOT / service_dir

    proc = await asyncio.create_subprocess_exec(
        settings.interactive_service_python,
        "main.py",
        "--mode", "watchlist",
        "--symbols", ",".join(symbols),
        "--adhoc",
        "--log-level", "WARNING",
        cwd=str(service_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=settings.interactive_service_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise InteractiveServiceError(
            f"interactive-service timed out after {settings.interactive_service_timeout_seconds}s "
            "(is IB Gateway/TWS running and responsive?)"
        ) from exc

    if proc.returncode != 0:
        raise InteractiveServiceError(
            f"interactive-service exited {proc.returncode}: "
            f"{stderr.decode(errors='replace').strip()[-500:]}"
        )

    lines = [line for line in stdout.decode(errors="replace").splitlines() if line.strip()]
    if not lines:
        raise InteractiveServiceError("interactive-service produced no output path")
    output_path = Path(lines[-1].strip())
    if not output_path.is_absolute():
        # main.py prints a path relative to its own cwd (service_dir), not ours.
        output_path = service_dir / output_path

    try:
        payload = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise InteractiveServiceError(f"could not read output file {output_path}: {exc}") from exc

    return {rec["symbol"]: rec for rec in payload.get("stocks", []) if "symbol" in rec}


async def fetch(
    symbols: list[str], fields: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, float | str | None]], str | None]:
    """Fetch interactive-service data for the given symbols.

    Returns ({symbol: {field_key: value}}, error). On failure every symbol/field
    is simply absent (None) and `error` carries a human-readable message for the UI.
    """
    try:
        records = await _run_adhoc(symbols)
    except InteractiveServiceError as exc:
        logger.warning("interactive_service_source failed: %s", exc)
        return {}, str(exc)
    except Exception as exc:  # never let a single source crash the whole comparison
        logger.exception("interactive_service_source: unexpected error")
        return {}, f"unexpected error: {exc}"

    result: dict[str, dict[str, float | str | None]] = {}
    for symbol in symbols:
        record = records.get(symbol, {})
        values: dict[str, float | str | None] = {}
        for field in fields:
            cfg = field.get("interactive_service")
            if not cfg:
                continue
            values[field["key"]] = resolve_ibk_path_list(record, cfg["path"])
        result[symbol] = values

    missing = set(symbols) - set(records.keys())
    error = f"no data returned for: {', '.join(sorted(missing))}" if missing else None
    return result, error
