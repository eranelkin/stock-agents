from __future__ import annotations

import json

import aiofiles

from ai_service.utils.logger import get_logger

logger = get_logger(__name__)


async def load_prompts(path: str = "Prompts.json") -> dict[str, str]:
    """Load and return the prompts dict from a JSON file.

    Args:
        path: Path to the Prompts.json file.

    Returns:
        Mapping of prompt_id to prompt string.
    """
    async with aiofiles.open(path) as f:
        content = await f.read()
    prompts: dict[str, str] = json.loads(content)
    if not prompts:
        raise ValueError(f"{path} contains no prompts")
    logger.info(f"Loaded {len(prompts)} prompts from {path}")
    return prompts
