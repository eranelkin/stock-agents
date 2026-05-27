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
    ticker: str,
    output_dir: str,
    output_format: str,
) -> None:
    """Serialize pipeline output to a YAML or JSON file.

    Args:
        data: The output dict to serialize.
        ticker: Ticker symbol, used in the filename.
        output_dir: Directory to write into (created if absent).
        output_format: "yaml" or "json".
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ext = output_format.lower()
    path = Path(output_dir) / f"output_{ticker}.{ext}"

    if ext == "yaml":
        content = yaml.dump(data, allow_unicode=True, sort_keys=False)
    else:
        content = json.dumps(data, indent=2)

    async with aiofiles.open(path, "w") as f:
        await f.write(content)

    logger.info(f"Output written to {path}", extra={"ticker": ticker})
