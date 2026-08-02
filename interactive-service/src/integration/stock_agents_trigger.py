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
    model_names: list[str] | None = None,
) -> None:
    """Read the interactive-service output file and submit a run to stock-agents backend.

    Fetches active model IDs from the backend (filtered by model_names if provided),
    then calls POST /runs with the full stock dicts as the tickers payload.
    Errors are logged but never raised so they never interrupt the main pipeline.
    """
    try:
        with open(output_path) as f:
            data = json.load(f)

        stocks: list[dict] = data.get("stocks", [])
        if not stocks:
            log.warning("stock_agents_trigger: output file has no stocks — skipping")
            return

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
        resp.raise_for_status()
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
