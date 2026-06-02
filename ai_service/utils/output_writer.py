from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiofiles
import yaml

from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


async def write_output(
    data: dict[str, Any],
    entity_name: str,
    output_dir: str,
    output_format: str,
    output_prefix: str = "output_",
) -> None:
    """Write a single entity's pipeline output to a YAML or JSON file.

    Args:
        data: The output dict to serialize.
        entity_name: Entity identifier used in the filename (ticker symbol or sector name).
        output_dir: Directory to write into (created if absent).
        output_format: "yaml" or "json".
        output_prefix: Filename prefix, e.g. "output_" → output_AAPL.yaml.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ext = output_format.lower()
    path = Path(output_dir) / f"{output_prefix}{entity_name}.{ext}"

    if ext == "yaml":
        content = yaml.dump(data, allow_unicode=True, sort_keys=False)
    else:
        content = json.dumps(data, indent=2)

    async with aiofiles.open(path, "w") as f:
        await f.write(content)

    logger.info(f"Output written to {path}", extra={"entity": entity_name})


async def write_combined_output(
    data: dict[str, Any],
    filename: str,
    output_dir: str,
    output_format: str,
) -> None:
    """Write all entities as a single combined YAML or JSON file.

    Used for pipelines with output_mode="single_file" (e.g. sectors → sectors.yaml).

    Args:
        data: Dict keyed by entity name, each value is the entity's output.
        filename: Output filename without extension, e.g. "sectors" → sectors.yaml.
        output_dir: Directory to write into (created if absent).
        output_format: "yaml" or "json".
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ext = output_format.lower()
    path = Path(output_dir) / f"{filename}.{ext}"

    if ext == "yaml":
        content = yaml.dump(data, allow_unicode=True, sort_keys=False)
    else:
        content = json.dumps(data, indent=2)

    async with aiofiles.open(path, "w") as f:
        await f.write(content)

    logger.info(f"Combined output written to {path}")
