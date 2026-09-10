"""Trigger a stock-agents run via the backend API after an interactive-service output is written."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import requests

log = logging.getLogger(__name__)


def trigger_stock_agents_run(
    output_path: Path,
    backend_url: str,
    run_name_prefix: str,
    enrichment_enabled: bool,
    candle_frequency: str,
    model_ids: list[str] | None = None,
    model_names: list[str] | None = None,
    run_id: str | None = None,
) -> None:
    """Read the interactive-service output file and submit a run to stock-agents backend.

    If run_id is provided, calls POST /runs/{run_id}/start-ai to continue an existing
    'fetching' run (created when the screener was triggered). Otherwise creates a new run
    via POST /runs.

    If model_ids is provided, uses them directly (UI selection takes priority).
    Otherwise fetches active model IDs from the backend, filtered by model_names if set.
    Errors are logged but never raised so they never interrupt the main pipeline.
    """
    try:
        with open(output_path) as f:
            data = json.load(f)

        stocks: list[dict] = data.get("stocks", [])
        if not stocks:
            log.warning("stock_agents_trigger: output file has no stocks — skipping")
            if run_id:
                try:
                    resp = requests.post(
                        f"{backend_url}/runs/{run_id}/fail",
                        json={"error": "No stocks passed the screener filters"},
                        timeout=10,
                    )
                    if resp.ok:
                        log.info("stock_agents_trigger: run %s marked as failed (empty screener output)", run_id)
                    else:
                        log.error("stock_agents_trigger: could not fail run %s — HTTP %d", run_id, resp.status_code)
                except Exception:
                    log.exception("stock_agents_trigger: error marking run %s as failed", run_id)
            return

        if model_ids:
            log.info("stock_agents_trigger: using %d model(s) from caller", len(model_ids))
        else:
            resp = requests.get(
                f"{backend_url}/models",
                params={"active": "true"},
                timeout=10,
            )
            resp.raise_for_status()
            models: list[dict] = resp.json()

            if not models:
                log.warning("stock_agents_trigger: no active models in backend — skipping")
                return

            if model_names:
                wanted = {n.lower() for n in model_names}
                models = [m for m in models if m.get("name", "").lower() in wanted]
                if not models:
                    log.warning(
                        "stock_agents_trigger: none of the configured model_names %s matched "
                        "active models — skipping",
                        model_names,
                    )
                    return

            model_ids = [m["id"] for m in models]

        if run_id:
            # Continue an existing 'fetching' run created when the screener was triggered.
            payload = {
                "model_ids": model_ids,
                "tickers": stocks,
                "candle_frequency": candle_frequency,
                "enrichment_enabled": enrichment_enabled,
            }
            resp = requests.post(f"{backend_url}/runs/{run_id}/start-ai", json=payload, timeout=30)
            if not resp.ok:
                detail = resp.json().get("detail", resp.text) if resp.content else resp.reason
                log.error(
                    "stock_agents_trigger: backend rejected start-ai — HTTP %d: %s",
                    resp.status_code,
                    detail,
                )
                return
            run = resp.json()
            log.info(
                "stock_agents_trigger: started AI for run id=%s with %d stocks",
                run.get("id"),
                len(stocks),
            )
        else:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            run_name = f"{run_name_prefix} — {ts} ({len(stocks)} stocks)"
            payload = {
                "model_ids": model_ids,
                "name": run_name,
                "tickers": stocks,
                "candle_frequency": candle_frequency,
                "enrichment_enabled": enrichment_enabled,
            }
            resp = requests.post(f"{backend_url}/runs", json=payload, timeout=30)
            if not resp.ok:
                detail = resp.json().get("detail", resp.text) if resp.content else resp.reason
                log.error(
                    "stock_agents_trigger: backend rejected run — HTTP %d: %s",
                    resp.status_code,
                    detail,
                )
                return
            run = resp.json()
            log.info(
                "stock_agents_trigger: submitted run id=%s name=%r with %d stocks",
                run.get("id"),
                run_name,
                len(stocks),
            )

    except requests.exceptions.ConnectionError:
        log.error(
            "stock_agents_trigger: could not reach stock-agents backend at %s — "
            "is it running?",
            backend_url,
        )
    except Exception:
        log.exception("stock_agents_trigger: unexpected error — run not submitted")
