from __future__ import annotations

import asyncio
import json
import yaml
from pathlib import Path
from typing import Any

from ai_service.config import settings
from ai_service.models.llm_client import LLMClient
from ai_service.models.search_client import SearchClient
from ai_service.pipeline import Pipeline
from ai_service.schemas.input import CeoInput
from ai_service.schemas.run import ModelConfig, PromptConfig
from ai_service.utils.logger import get_logger
from ai_service.utils.output_writer import write_output
from ai_service.utils.run_logger import RunLogger

logger = get_logger(__name__)


def _parse_numeric(value: Any) -> float | None:
    """Parse a raw or formatted numeric value (e.g. '39.33M', '90.28%', 307040) to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    s = value.strip().upper().replace(",", "")
    if not s or s.startswith("N"):  # catches "N/A", "Not available..."
        return None
    multiplier = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s.endswith("T"):
        s, multiplier = s[:-1], 1_000_000_000_000.0
    elif s.endswith("B"):
        s, multiplier = s[:-1], 1_000_000_000.0
    elif s.endswith("M"):
        s, multiplier = s[:-1], 1_000_000.0
    elif s.endswith("K"):
        s, multiplier = s[:-1], 1_000.0
    try:
        return float(s) * multiplier
    except ValueError:
        return None


# Maps yfinance/enrichment sector names (lowercase) to ETF sector names (lowercase)
# used in the market-data file, covering common mismatches.
_SECTOR_ALIASES: dict[str, str] = {
    "computers": "information technology",
    "technology": "information technology",
    "semiconductors": "semiconductors & semiconductor equipment",
    "telecom": "telecommunications services",
    "telecommunications": "telecommunications services",
    "consumer electronics": "consumer discretionary",
    "internet content & information": "communication services",
    "software—application": "software & services",
    "software—infrastructure": "software & services",
    "drug manufacturers": "pharmaceuticals",
    "aerospace & defense": "industrials",
    "medical devices": "health care equipment & supplies",
    # IB-specific sector name mappings
    "retail": "retailing",
    "software": "software & services",
    "internet": "communication services",
    "entertainment": "media & entertainment",
    "aerospace/defense": "industrials",
    "commercial services": "industrials",
    "diversified finan serv": "financial services",
    "investment companies": "capital markets",
    "machinery-constr&mining": "industrials",
    "mining": "metals & mining",
    "oil&gas services": "energy equipment & services",
    "healthcare": "health care",
}


class CeoManager:
    """Layer 5 — CEO pipeline manager.

    Runs CEO pipelines on a per-ticker streaming basis: as soon as StockAggregator
    completes a ticker (writes stock_{ticker}.yaml), that ticker's CEO pipeline(s)
    start immediately — without waiting for other tickers to finish.

    One Pipeline is spawned per ticker × model_config pair, matching the same
    fan-out pattern as the Layer 2 stocks pipeline.
    """

    def __init__(
        self,
        total_tickers: int,
        model_configs: list[ModelConfig],
        prompts: list[PromptConfig],
        semaphore: asyncio.Semaphore,
        run_dir: str,
        output_format: str,
        run_logger: RunLogger | None = None,
    ) -> None:
        self._total = total_tickers
        self._model_configs = model_configs
        self._prompts = prompts
        self._semaphore = semaphore
        self._run_dir = run_dir
        self._output_format = output_format
        self._run_logger = run_logger
        self._queue: asyncio.Queue[tuple[str, dict[str, Any], dict[str, Any]]] = asyncio.Queue()
        self._sector_etf_map: dict[str, dict[str, Any]] = self._build_sector_etf_map()

    def _build_sector_etf_map(self) -> dict[str, dict[str, Any]]:
        """Build lowercase sector-name → ETF-data dict from the latest market-data file."""
        d = Path(settings.market_data_output_dir)
        if not d.exists():
            return {}
        files = sorted(d.glob("market_*.json"), reverse=True)
        if not files:
            return {}
        try:
            symbols = json.loads(files[0].read_text()).get("symbols", {})
        except Exception as exc:
            logger.warning("Failed to load market-data for sector ETF map: %s", exc)
            return {}
        mapping: dict[str, dict[str, Any]] = {}
        for etf_data in symbols.values():
            sector = etf_data.get("sector", "")
            if sector and etf_data.get("type") == "sector_etf":
                mapping[sector.lower()] = etf_data
        logger.info("Sector ETF map built: %d entries from %s", len(mapping), files[0].name)
        return mapping

    def _lookup_sector_etf(self, sector: str | None) -> dict[str, Any] | None:
        """Return the ETF data dict for the given sector name, or None if not found."""
        if not sector:
            return None
        key = sector.lower()
        data = self._sector_etf_map.get(key) or \
               self._sector_etf_map.get(_SECTOR_ALIASES.get(key, ""))
        if not data:
            logger.info("No sector ETF found for sector '%s'", sector)
            return None
        return {
            "etf": data.get("symbol"),
            "name": data.get("name"),
            "sector": data.get("sector"),
            "quote": data.get("quote"),
            "pre_market": data.get("pre_market"),
            "sentiment": data.get("sentiment"),
        }

    async def _load_macro_analysis(self) -> dict[str, Any] | None:
        """Wait for macro.yaml to appear in the run directory and return its parsed content.

        Retries for up to 30 seconds so CEO doesn't start before macro pipeline finishes.
        Returns None if macro was not configured or did not complete in time.
        """
        macro_path = Path(self._run_dir) / "macro.yaml"
        for attempt in range(15):
            if macro_path.exists():
                try:
                    data = yaml.safe_load(macro_path.read_text())
                    logger.info("Macro analysis loaded from %s", macro_path.name)
                    return data
                except Exception as exc:
                    logger.warning("Failed to parse macro.yaml: %s", exc)
                    return None
            if attempt == 0:
                logger.info("Waiting for macro.yaml in %s ...", self._run_dir)
            await asyncio.sleep(2)
        logger.warning("macro.yaml not found after 30s — CEO will proceed without macro context")
        return None

    async def on_ticker_ready(
        self,
        ticker: str,
        agents: dict[str, Any],
        entity_dict: dict[str, Any] | None = None,
    ) -> None:
        """Called by StockAggregator when a ticker's aggregated data is ready."""
        await self._queue.put((ticker, agents, entity_dict or {}))
        logger.info("CEO ticker enqueued", extra={"ticker": ticker})

    async def run(self) -> None:
        """Consume the queue and spawn CEO Pipeline tasks as tickers arrive."""
        if not self._prompts:
            return

        macro_analysis = await self._load_macro_analysis()

        tasks: list[asyncio.Task[None]] = []
        for _ in range(self._total):
            ticker, agents, entity_dict = await self._queue.get()
            sector = entity_dict.get("sector")
            sector_etf = self._lookup_sector_etf(sector)
            if sector_etf:
                logger.info(
                    "CEO sector ETF resolved: %s → %s",
                    sector, sector_etf.get("etf"),
                    extra={"ticker": ticker},
                )
            _pre_mkt_vol = _parse_numeric(entity_dict.get("pre_market_volume"))
            _float_pct = _parse_numeric(entity_dict.get("float_pct"))
            _shares_out = _parse_numeric(entity_dict.get("shares_outstanding"))
            float_turnover_ratio: float | None = None
            if _pre_mkt_vol and _float_pct and _shares_out:
                float_shares = (_float_pct / 100) * _shares_out
                if float_shares > 0:
                    float_turnover_ratio = round(_pre_mkt_vol / float_shares, 4)

            entity = CeoInput(
                symbol=ticker,
                agents=agents,
                macro_analysis=macro_analysis,
                sector_etf=sector_etf,
                float_turnover_ratio=float_turnover_ratio,
            )
            for mc in self._model_configs:
                tasks.append(asyncio.create_task(self._run_one(entity, mc)))

        if tasks:
            await asyncio.gather(*tasks)

    async def _run_one(self, entity: CeoInput, mc: ModelConfig) -> None:
        """Run one CEO pipeline for a single ticker × model pair."""
        search_client = SearchClient(run_logger=self._run_logger)
        pipeline = Pipeline(
            entity=entity,
            entity_name=entity.symbol,
            prompts=self._prompts,
            pipeline_semaphore=self._semaphore,
            llm_client=LLMClient(mc, run_logger=self._run_logger),
            model_name=mc.name,
            search_client=search_client,
            run_logger=self._run_logger,
            pipeline_type="ceo",
            run_dir=self._run_dir,
            output_prefix="CEO_",
        )
        output = await pipeline.run()
        await write_output(
            data=output.model_dump(),
            entity_name=output.ticker,
            output_dir=self._run_dir,
            output_format=self._output_format,
            output_prefix="CEO_",
        )
        logger.info(
            "CEO pipeline output written",
            extra={"ticker": entity.symbol, "model": mc.name},
        )
