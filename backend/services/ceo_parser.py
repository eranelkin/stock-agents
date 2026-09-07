from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


def try_parse_raw_output(raw: str) -> dict | None:
    """Parse a (possibly truncated) JSON string from raw_output.

    Tries the string as-is first, then attempts structural repair by stripping
    any trailing incomplete key and closing unclosed braces/brackets.
    Returns a flat dict of CEO fields (unwrapping one level of nesting if needed).
    """
    def _extract(obj: dict) -> dict:
        # Unwrap {"symbol": {...}} or {"key": {...}} → use inner dict
        for v in obj.values():
            if isinstance(v, dict) and v:
                return v
        return obj

    # 1. Try as-is (valid complete JSON)
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return _extract(result)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Repair: strip trailing incomplete key like `"key":` or `"key": `
    text = re.sub(r',?\s*"[^"]*":\s*$', '', raw.strip())

    # Count unclosed braces and brackets
    opens_brace = text.count('{') - text.count('}')
    opens_bracket = text.count('[') - text.count(']')
    if opens_brace < 0 or opens_bracket < 0:
        return None

    repaired = text + ']' * opens_bracket + '}' * opens_brace
    try:
        result = json.loads(repaired)
        if isinstance(result, dict):
            return _extract(result)
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def parse_ceo_file(file_path: Path) -> dict | None:
    """Extract the stock analysis dict from a CEO_*.yaml or CEO_*.json output file.

    Handles three LLM output patterns:
    - Each analysis field as a separate list item under `stocks` (old JSON pattern)
    - Analysis fields nested under a key (e.g. "symbol") in agent_data (current YAML pattern)
    - parse_error: true with raw_output containing a JSON string (LLM returned invalid JSON)
    All are merged into one flat dict.
    """
    try:
        with open(file_path) as f:
            doc = yaml.safe_load(f) if file_path.suffix == ".yaml" else json.load(f)
        for agent_data in doc.get("agents", {}).values():
            if not isinstance(agent_data, dict):
                continue
            merged: dict = {}
            _SKIP = {"stocks", "raw_output", "parse_error", "reasoning"}
            # Old JSON pattern: stocks is a list of single-key dicts
            for item in agent_data.get("stocks") or []:
                if isinstance(item, dict):
                    merged.update(item)
            # Current YAML pattern: data is a dict nested under a key (e.g. "symbol"),
            # or flat sibling keys alongside stocks
            for k, v in agent_data.items():
                if k in _SKIP:
                    continue
                if isinstance(v, dict):
                    merged.update(v)
                else:
                    merged.setdefault(k, v)
            # Fallback: parse_error pattern — LLM returned a JSON string in raw_output
            # The string may be truncated mid-stream, so we attempt repair before parsing.
            if not merged and agent_data.get("parse_error") and agent_data.get("raw_output"):
                raw_str = agent_data["raw_output"]
                parsed = try_parse_raw_output(raw_str)
                if parsed:
                    merged.update(parsed)
            if merged:
                return merged
    except Exception:
        pass
    return None
