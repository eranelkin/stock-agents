from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ai_service.schemas.input import TickerInput
from ai_service.schemas.macro_input import MacroInput
from ai_service.schemas.sector_input import SectorInput


@dataclass
class PipelineTypeConfig:
    """Configuration for one pipeline type in the multi-pipeline registry.

    Adding a new pipeline type = one new PipelineTypeConfig in PIPELINE_REGISTRY.
    No other code changes required.
    """

    name: str
    entity_schema: type
    prompt_category: str
    output_mode: Literal["per_entity", "single_file"]
    output_prefix: str
    # data_source_key: attribute name on settings for the JSON file path.
    # Ignored when use_request_entities=True.
    data_source_key: str = ""
    # single_file_name: output filename (without extension) for single_file mode.
    single_file_name: str = ""
    dependencies: list[str] = field(default_factory=list)
    # required: if False, pipeline is skipped silently when no prompts are configured.
    required: bool = True
    # use_request_entities: if True, entities come from the RunRequest tickers list
    # instead of a JSON file. Used for the stocks pipeline.
    use_request_entities: bool = False
    # persist_to_db: Phase 1 — only stocks persist. Phase 2 will add SectorResult table.
    persist_to_db: bool = False
    # triggers_aggregation: if True, each completed per-entity output is forwarded to
    # StockAggregator. Set True for any pipeline whose agent data should appear in
    # agg_{ticker}.yaml.
    triggers_aggregation: bool = False


PIPELINE_REGISTRY: list[PipelineTypeConfig] = [
    PipelineTypeConfig(
        name="stocks",
        entity_schema=TickerInput,
        prompt_category="agents",
        output_mode="per_entity",
        output_prefix="stock_",
        dependencies=[],
        required=True,
        use_request_entities=True,
        persist_to_db=True,
        triggers_aggregation=True,
    ),
    PipelineTypeConfig(
        name="sectors",
        data_source_key="sectors_json",
        entity_schema=SectorInput,
        prompt_category="sectors",
        output_mode="single_file",
        output_prefix="",
        single_file_name="sectors",
        dependencies=[],
        required=False,
        use_request_entities=False,
        persist_to_db=False,
    ),
    PipelineTypeConfig(
        name="macro",
        data_source_key="macro_json",
        entity_schema=MacroInput,
        prompt_category="macro",
        output_mode="single_file",
        output_prefix="",
        single_file_name="macro",
        dependencies=[],
        required=False,
        use_request_entities=False,
        persist_to_db=False,
    ),
]
