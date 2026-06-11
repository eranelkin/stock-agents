from __future__ import annotations

import asyncio
import html as _html_mod
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles


# ── Visual config ──────────────────────────────────────────────────────────────

_TYPE_META: dict[str, tuple[str, str, str]] = {
    "run_start":          ("▶▶", "run",       "RUN START"),
    "run_end":            ("■■", "run",       "RUN END"),
    "pipeline_start":     ("▶",  "pipeline",  "PIPELINE"),
    "pipeline_end":       ("■",  "pipeline",  "PIPELINE END"),
    "llm_request":        ("⬆",  "llm-req",   "LLM REQUEST"),
    "llm_response_ok":    ("✓",  "llm-ok",    "LLM RESPONSE"),
    "llm_response_error": ("✗",  "llm-err",   "LLM ERROR"),
    "search_request":     ("⌕",  "srch-req",  "SEARCH REQ"),
    "search_response":    ("◉",  "srch-resp", "SEARCH RESP"),
}

_ENTITY_COLORS = ["#4a9eff", "#34d399", "#a78bfa", "#fb923c", "#f472b6", "#38bdf8"]


# ── Event dataclass ────────────────────────────────────────────────────────────

@dataclass
class _Event:
    seq: int
    ts: str
    type: str
    pipeline_type: str
    entity: str
    model: str
    pipeline_id: str
    agent_id: str
    prompt_title: str
    status: str
    duration_ms: int
    payload: dict[str, Any]


# ── RunLogger ──────────────────────────────────────────────────────────────────

class RunLogger:
    """Streams run events to an HTML log file in real time.

    Events are flushed to disk immediately as they occur. The HTML page embeds
    polling JS that fetches new rows every 2 seconds and appends them without a
    full page reload, enabling live monitoring during an active run.

    Args:
        log_path: Absolute or relative path for the output HTML file.
        run_id: The run UUID string; embedded in the polling fetch URL.
    """

    def __init__(self, log_path: str, run_id: str = "") -> None:
        self._path = log_path
        self._run_id = run_id
        self._lock = asyncio.Lock()
        self._seq = 0
        self._entity_colors: dict[str, str] = {}
        self._fh: Any = None
        self._mode = ""
        self._stat_llm = 0
        self._stat_ok = 0
        self._stat_err = 0
        self._stat_ptok = 0
        self._stat_ctok = 0
        self._stat_ttok = 0
        self._total_dur_ms = 0
        self._started_ms = 0

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def open(self, run_id: str, started_at: str) -> None:
        """Write the HTML header and open the file handle for streaming."""
        async with self._lock:
            self._started_ms = int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp() * 1000)
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._fh = await aiofiles.open(self._path, "w", encoding="utf-8")
            await self._fh.write(self._build_header(run_id, started_at))
            await self._fh.flush()

    async def close(self) -> None:
        """Write the closing HTML (final stats + done flag) and close the file."""
        async with self._lock:
            if self._fh:
                await self._fh.write(self._build_footer())
                await self._fh.flush()
                await self._fh.close()
                self._fh = None

    # ── Run-level events ───────────────────────────────────────────────────────

    async def run_start(
        self,
        *,
        mode: str,
        models: list[str],
        tickers: list[str],
        agent_prompts: list[str],
        sector_prompts: list[str],
        ceo_prompts: list[str] | None = None,
    ) -> None:
        self._mode = mode
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="run_start",
                pipeline_type="", entity="", model="", pipeline_id="",
                agent_id="", prompt_title="", status="started", duration_ms=-1,
                payload={
                    "mode": mode, "models": models, "tickers": tickers,
                    "agent_prompts": agent_prompts, "sector_prompts": sector_prompts,
                    "ceo_prompts": ceo_prompts or [],
                },
            ))

    async def run_end(self, *, total_duration_ms: int) -> None:
        self._total_dur_ms = total_duration_ms
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="run_end",
                pipeline_type="", entity="", model="", pipeline_id="",
                agent_id="", prompt_title="", status="completed",
                duration_ms=total_duration_ms,
                payload={"total_duration_ms": total_duration_ms},
            ))

    # ── Pipeline-level events ──────────────────────────────────────────────────

    async def pipeline_start(
        self,
        *,
        pipeline_type: str,
        entity: str,
        model: str,
        pipeline_id: str,
    ) -> None:
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="pipeline_start",
                pipeline_type=pipeline_type, entity=entity, model=model,
                pipeline_id=pipeline_id, agent_id="", prompt_title="",
                status="started", duration_ms=-1, payload={},
            ))

    async def pipeline_end(
        self,
        *,
        pipeline_type: str,
        entity: str,
        model: str,
        pipeline_id: str,
        duration_ms: int,
        output_file: str,
    ) -> None:
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="pipeline_end",
                pipeline_type=pipeline_type, entity=entity, model=model,
                pipeline_id=pipeline_id, agent_id="", prompt_title="",
                status="completed", duration_ms=duration_ms,
                payload={"output_file": output_file, "duration_ms": duration_ms},
            ))

    # ── Agent-level events ─────────────────────────────────────────────────────

    async def search_request(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        query: str,
        pipeline_id: str = "",
        pipeline_type: str = "",
        entity: str = "",
    ) -> None:
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="search_request",
                pipeline_type=pipeline_type, entity=entity, model="",
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="", duration_ms=-1,
                payload={"query": query},
            ))

    async def search_response(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        sources: list[str],
        pipeline_id: str = "",
        pipeline_type: str = "",
        entity: str = "",
    ) -> None:
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="search_response",
                pipeline_type=pipeline_type, entity=entity, model="",
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="ok", duration_ms=duration_ms,
                payload={"sources": sources, "result_count": len(sources)},
            ))

    async def llm_request(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        model: str,
        system_prompt: str,
        user_message: str,
        pipeline_id: str = "",
        pipeline_type: str = "",
        entity: str = "",
    ) -> None:
        self._stat_llm += 1
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="llm_request",
                pipeline_type=pipeline_type, entity=entity, model=model,
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="", duration_ms=-1,
                payload={"system_prompt": system_prompt, "user_message": user_message},
            ))

    async def llm_response_ok(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        tokens: dict[str, int],
        response_text: str,
        pipeline_id: str = "",
        pipeline_type: str = "",
        entity: str = "",
    ) -> None:
        pt = tokens.get("prompt_tokens", 0)
        ct = tokens.get("completion_tokens", 0)
        tt = tokens.get("total_tokens", 0)
        self._stat_ok += 1
        self._stat_ptok += pt
        self._stat_ctok += ct
        self._stat_ttok += tt
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="llm_response_ok",
                pipeline_type=pipeline_type, entity=entity, model="",
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="ok", duration_ms=duration_ms,
                payload={"tokens": tokens, "response_text": response_text},
            ))

    async def llm_response_error(
        self,
        *,
        agent_id: str,
        prompt_title: str,
        duration_ms: int,
        error: str,
        pipeline_id: str = "",
        pipeline_type: str = "",
        entity: str = "",
    ) -> None:
        self._stat_err += 1
        async with self._lock:
            self._seq += 1
            await self._append(_Event(
                seq=self._seq, ts=_ts(), type="llm_response_error",
                pipeline_type=pipeline_type, entity=entity, model="",
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="error", duration_ms=duration_ms,
                payload={"error": error},
            ))

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _append(self, e: _Event) -> None:
        """Write the two <tr> rows for this event immediately. Must be called within lock."""
        if not self._fh:
            return
        entity, color = self._resolve_color(e)
        await self._fh.write(_render_row(e, entity, color) + "\n")
        await self._fh.write(_render_inline_detail(e, entity, color) + "\n")
        await self._fh.flush()

    def _resolve_color(self, e: _Event) -> tuple[str, str]:
        entity = e.entity
        if entity and entity not in self._entity_colors:
            self._entity_colors[entity] = _ENTITY_COLORS[len(self._entity_colors) % len(_ENTITY_COLORS)]
        return entity, (self._entity_colors.get(entity, "#6b7280") if entity else "#6b7280")

    def _build_header(self, run_id: str, started_at: str) -> str:
        run_id_short = run_id[:8] if len(run_id) > 8 else run_id
        polling_run_id = self._run_id or run_id
        return (
            f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>Run Log — {_h(run_id_short)}</title>\n'
            f'<style>{_CSS}</style>\n'
            f'<script>window.__RUN_START_MS__={self._started_ms};</script>\n'
            f'<script>\n{_JS}\n{_polling_js(polling_run_id)}\n</script>\n'
            f'</head>\n<body>\n\n'
            f'<div class="header-card">\n'
            f'  <div class="header-left">\n'
            f'    <div class="header-title">STOCK-AGENTS &middot; RUN LOG</div>\n'
            f'    <div class="header-meta">\n'
            f'      <span class="meta-item"><span class="meta-label">Run ID</span>'
            f'<span class="meta-value mono">{_h(run_id)}</span></span>\n'
            f'      <span class="meta-item"><span class="meta-label">Started</span>'
            f'<span class="meta-value">{_h(started_at)}</span></span>\n'
            f'      <span class="meta-item"><span class="meta-label">Duration</span>'
            f'<span class="meta-value" id="meta-duration">—</span></span>\n'
            f'      <span class="meta-item"><span class="meta-label">Mode</span>'
            f'<span class="meta-value" id="meta-mode">—</span></span>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'  <div class="header-stats">\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-rpm-min">—</span>'
            f'<span class="hstat-label">Min RPM</span></div>\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-rpm-max">—</span>'
            f'<span class="hstat-label">Max RPM</span></div>\n'
            f'    <div class="hstat-sep"></div>\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-ttok">0</span>'
            f'<span class="hstat-label">Total Tokens</span></div>\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-ptok">0</span>'
            f'<span class="hstat-label">Prompt</span></div>\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-ctok">0</span>'
            f'<span class="hstat-label">Completion</span></div>\n'
            f'    <div class="hstat-sep"></div>\n'
            f'    <div class="hstat-item"><span class="hstat-value" id="hstat-tpm">—</span>'
            f'<span class="hstat-label">Tokens / min</span></div>\n'
            f'  </div>\n'
            f'  <div class="run-status-badge" id="run-status-badge">'
            f'<span class="run-spinner"></span><span>RUNNING</span></div>\n'
            f'</div>\n\n'
            f'<div class="stats-bar">\n'
            f'  <div class="stat-item"><span class="stat-value" id="stat-llm">0</span>'
            f'<span class="stat-label">LLM Calls</span></div>\n'
            f'  <div class="stat-item success"><span class="stat-value" id="stat-ok">0</span>'
            f'<span class="stat-label">Success</span></div>\n'
            f'  <div class="stat-item error"><span class="stat-value" id="stat-err">0</span>'
            f'<span class="stat-label">Errors</span></div>\n'
            f'  <div class="filter-group">\n'
            f'    <div class="filter-col">\n'
            f'      <span class="filter-label">Ticker</span>\n'
            f'      <div class="filter-dropdown" id="dd-tickers">\n'
            f'        <button class="filter-btn" id="dd-tickers-btn" onclick="toggleDropdown(\'dd-tickers\')">'
            f'<span id="dd-tickers-label">All Tickers</span><span class="dd-arrow">&#x25BE;</span></button>\n'
            f'        <div class="filter-panel" id="dd-tickers-panel" style="display:none"></div>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'    <div class="filter-col">\n'
            f'      <span class="filter-label">Pipeline</span>\n'
            f'      <div class="filter-dropdown" id="dd-types">\n'
            f'        <button class="filter-btn" id="dd-types-btn" onclick="toggleDropdown(\'dd-types\')">'
            f'<span id="dd-types-label">All Types</span><span class="dd-arrow">&#x25BE;</span></button>\n'
            f'        <div class="filter-panel" id="dd-types-panel" style="display:none"></div>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'    <div class="filter-col">\n'
            f'      <span class="filter-label">Event Type</span>\n'
            f'      <div class="filter-dropdown" id="dd-etypes">\n'
            f'        <button class="filter-btn" id="dd-etypes-btn" onclick="toggleDropdown(\'dd-etypes\')">'
            f'<span id="dd-etypes-label">All Event Types</span><span class="dd-arrow">&#x25BE;</span></button>\n'
            f'        <div class="filter-panel" id="dd-etypes-panel" style="display:none"></div>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'    <div class="filter-col">\n'
            f'      <span class="filter-label">Agent</span>\n'
            f'      <div class="filter-dropdown" id="dd-prompts">\n'
            f'        <button class="filter-btn" id="dd-prompts-btn" onclick="toggleDropdown(\'dd-prompts\')">'
            f'<span id="dd-prompts-label">All Prompts</span><span class="dd-arrow">&#x25BE;</span></button>\n'
            f'        <div class="filter-panel" id="dd-prompts-panel" style="display:none"></div>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'    <div class="filter-col" style="justify-content:flex-end">\n'
            f'      <span class="filter-label">&nbsp;</span>\n'
            f'      <button class="clear-filters-btn" id="clear-filters-btn" onclick="clearFilters()" disabled>'
            f'Clear Filters</button>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'</div>\n\n'
            f'<div class="section-heading" id="events-table-anchor">Events</div>\n'
            f'<div class="table-wrapper">\n'
            f'<table id="events-table">\n'
            f'  <thead>\n'
            f'    <tr>\n'
            f'      <th>#</th><th>Time</th><th>Pipeline</th>\n'
            f'      <th>Prompt / Detail</th><th>Entity</th><th>Type</th><th>Model</th><th>Duration</th>\n'
            f'    </tr>\n'
            f'  </thead>\n'
            f'  <tbody id="events-body">\n'
        )

    def _build_footer(self) -> str:
        dur = _fmt_duration(self._total_dur_ms) if self._total_dur_ms else "—"
        tpm = round(self._stat_ttok / (self._total_dur_ms / 60000)) if self._total_dur_ms > 0 else 0
        vals = {
            "stat-llm":      str(self._stat_llm),
            "stat-ok":       str(self._stat_ok),
            "stat-err":      str(self._stat_err),
            "hstat-ttok":    f"{self._stat_ttok:,}",
            "hstat-ptok":    f"{self._stat_ptok:,}",
            "hstat-ctok":    f"{self._stat_ctok:,}",
            "hstat-tpm":     f"{tpm:,}" if tpm > 0 else "—",
            "meta-duration": _h(dur),
            "meta-mode":     _h(self._mode),
        }
        vals_js = json.dumps(vals)
        return (
            "  </tbody>\n</table>\n</div>\n\n"
            "<script>\n"
            "window.__RUN_DONE__ = true;\n"
            f"(function(){{ var v={vals_js};"
            " function a(){ for(var id in v){ var e=document.getElementById(id); if(e) e.textContent=v[id]; } }"
            " if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded',a); } else { a(); }"
            " })();\n"
            "</script>\n"
            "</body>\n</html>\n"
        )


# ── Module-level helpers ───────────────────────────────────────────────────────

def _ts() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"


def _h(s: Any) -> str:
    return _html_mod.escape(str(s))


def _fmt_duration(ms: int) -> str:
    if ms < 0:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def _model_short(model: str) -> str:
    return model.split("/")[-1] if "/" in model else model


def _pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        return text


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


# ── HTML rendering helpers ─────────────────────────────────────────────────────

def _render_row(e: _Event, entity: str, color: str) -> str:
    icon, css_cls, label = _TYPE_META.get(e.type, ("?", "unknown", e.type.upper()))
    if e.pipeline_type:
        if e.type in ("pipeline_start", "pipeline_end"):
            css_cls = f"pipeline-{e.pipeline_type}"
    dur = _fmt_duration(e.duration_ms)
    model_disp = _h(_model_short(e.model)) if e.model else "—"
    entity_disp = _h(entity) if entity else "—"
    prompt_disp = _h(e.prompt_title) if e.prompt_title else "—"

    extra = ""
    if e.type == "pipeline_end":
        chip_dur = _fmt_duration(e.payload.get("duration_ms", e.duration_ms))
        chip_label = f"[{e.pipeline_type.upper()}] {entity}" if e.pipeline_type else entity
        chip_json = _h(json.dumps({"entity": chip_label, "dur": chip_dur, "color": color}))
        extra = f" data-chip='{chip_json}'"
    elif e.type == "llm_response_ok":
        tok = e.payload.get("tokens", {})
        extra = (
            f' data-prompt-tok="{tok.get("prompt_tokens", 0)}"'
            f' data-comp-tok="{tok.get("completion_tokens", 0)}"'
            f' data-total-tok="{tok.get("total_tokens", 0)}"'
        )
    elif e.type == "run_start":
        extra = f' data-mode="{_h(e.payload.get("mode", ""))}"'
    elif e.type == "search_request":
        extra = f' data-search-query="{_h(e.payload.get("query", ""))}"'

    if e.pipeline_type:
        pipeline_disp = (
            f'<span class="pipeline-badge pipeline-badge-{e.pipeline_type}">'
            f'{e.pipeline_type.upper()}</span>'
        )
    else:
        pipeline_disp = '<span class="pipeline-badge-empty">&mdash;</span>'

    return (
        f'    <tr id="row-{e.seq}" class="event-row type-{css_cls}"'
        f' style="--row-color:{color}" onclick="toggleRow({e.seq})"{extra}'
        f' data-entity="{_h(entity)}" data-ptype="{_h(e.pipeline_type)}" data-prompt="{_h(e.prompt_title)}" data-etype="{_h(label)}">'
        f'<td class="col-seq"><span class="row-chevron">&#x25B6;</span>{e.seq}</td>'
        f'<td class="col-ts">{_h(e.ts)}</td>'
        f'<td class="col-pipeline">{pipeline_disp}</td>'
        f'<td class="col-prompt">{prompt_disp}</td>'
        f'<td class="col-entity"><span class="entity-dot" style="background:{color}"></span>'
        f'{entity_disp}</td>'
        f'<td class="col-type"><span class="type-badge {css_cls}">'
        f'<span class="ti">{icon}</span>{label}</span>'
        + (
            f'<button class="srch-info-btn" title="Show aggregated queries"'
            f' onmouseenter="showSearchPopup(this,{e.seq})"'
            f' onmouseleave="scheduleHideSearchPopup()"'
            f' onclick="event.stopPropagation()">&#x2139;</button>'
            if e.type == "search_request" else ""
        )
        + f'</td>'
        f'<td class="col-model">{model_disp}</td>'
        f'<td class="col-dur">{dur}</td>'
        f'</tr>'
    )


def _render_inline_detail(e: _Event, entity: str, color: str) -> str:
    """Collapsed <tr> rendered immediately after its event row; expands on click."""
    meta_parts: list[str] = []
    if e.ts:
        meta_parts.append(f'time: <span class="mono">{_h(e.ts)}</span>')
    if e.agent_id:
        meta_parts.append(f'agent: <span class="mono">{_h(e.agent_id)}</span>')
    if e.model:
        meta_parts.append(f'model: <span class="mono">{_h(e.model)}</span>')
    if e.pipeline_id:
        meta_parts.append(f'pipeline: <span class="mono">{_h(e.pipeline_id)}</span>')
    if e.duration_ms >= 0:
        meta_parts.append(f'duration: <strong>{_fmt_duration(e.duration_ms)}</strong>')
    meta = (
        f'<div class="card-meta">{"  ·  ".join(meta_parts)}</div>'
        if meta_parts else ""
    )
    body = _card_body(e)
    return (
        f'    <tr id="detail-row-{e.seq}" class="detail-row" style="display:none">'
        f'<td colspan="8" class="detail-cell" style="border-left-color:{color}">'
        f'{meta}{body}'
        f'</td></tr>'
    )


def _card_body(e: _Event) -> str:
    p = e.payload
    if e.type == "run_start":
        return _section_kv([
            ("Models",  ", ".join(p.get("models", [])) or "—"),
            ("Tickers", ", ".join(p.get("tickers", [])) or "—"),
            ("Agents",  ", ".join(p.get("agent_prompts", [])) or "none"),
            ("Sectors", ", ".join(p.get("sector_prompts", [])) or "none"),
            ("CEO",     ", ".join(p.get("ceo_prompts", [])) or "none"),
            ("Mode",    p.get("mode", "—")),
        ])
    if e.type == "pipeline_end" and p.get("output_file"):
        return _section_kv([("Output file", p["output_file"])], mono_val=True)
    if e.type == "llm_request":
        return _body_llm_request(p)
    if e.type == "llm_response_ok":
        return _body_llm_ok(p)
    if e.type == "llm_response_error":
        return (
            f'<div class="card-section">'
            f'<div class="section-label">Error</div>'
            f'<div class="error-block">{_h(p.get("error", ""))}</div>'
            f'</div>'
        )
    if e.type == "search_request":
        return _section_kv([("Query", p.get("query", ""))])
    if e.type == "search_response":
        sources = p.get("sources", [])
        items = "".join(f'<li class="src-item">{_h(s)}</li>' for s in sources)
        return (
            f'<div class="card-section">'
            f'<div class="section-label">{len(sources)} source(s)</div>'
            f'<ol class="src-list">{items}</ol>'
            f'</div>'
        )
    return ""


def _section_kv(pairs: list[tuple[str, str]], mono_val: bool = False) -> str:
    rows = "".join(
        f'<div class="kv-row">'
        f'<span class="kv-key">{_h(k)}</span>'
        f'<span class="kv-val{" mono" if mono_val else ""}">{_h(v)}</span>'
        f'</div>'
        for k, v in pairs
    )
    return f'<div class="card-section"><div class="kv-grid">{rows}</div></div>'


def _body_llm_request(p: dict[str, Any]) -> str:
    sys_prompt = p.get("system_prompt", "")
    user_msg = p.get("user_message", "")
    char_note = f' <span class="char-count">({len(sys_prompt):,} chars)</span>' if sys_prompt else ""
    user_display = _pretty_json(user_msg)
    user_block_cls = f'code-block{"  json-block" if _is_json(user_msg) else ""}'
    copy_btn = '<button class="copy-btn" onclick="copyBlock(this)">&#x2398; copy</button>'
    return (
        f'<div class="card-section">'
        f'<div class="section-label">System Prompt{char_note}{copy_btn}</div>'
        f'<pre class="code-block">{_h(sys_prompt)}</pre>'
        f'</div>'
        f'<div class="card-section">'
        f'<div class="section-label">Input{copy_btn}</div>'
        f'<pre class="{user_block_cls}">{_h(user_display)}</pre>'
        f'</div>'
    )


def _body_llm_ok(p: dict[str, Any]) -> str:
    tokens = p.get("tokens", {})
    pt = tokens.get("prompt_tokens", 0)
    ct = tokens.get("completion_tokens", 0)
    tt = tokens.get("total_tokens", 0)
    resp = p.get("response_text", "")
    display = _pretty_json(resp)
    resp_cls = f'code-block{"  json-block" if _is_json(resp) else ""}'
    token_str = (
        f'prompt=<strong>{pt:,}</strong>'
        f'&nbsp;&nbsp;completion=<strong>{ct:,}</strong>'
        f'&nbsp;&nbsp;total=<strong class="tok-total">{tt:,}</strong>'
    ) if tt else "tokens not reported"
    copy_btn = '<button class="copy-btn" onclick="copyBlock(this)">&#x2398; copy</button>'
    return (
        f'<div class="card-section">'
        f'<div class="token-line">{token_str}</div>'
        f'</div>'
        f'<div class="card-section">'
        f'<div class="section-label">Response{copy_btn}</div>'
        f'<pre class="{resp_cls}">{_h(display)}</pre>'
        f'</div>'
    )


# ── Polling JS ────────────────────────────────────────────────────────────────

def _polling_js(run_id: str) -> str:
    """Return the self-contained SSE script for live log updates."""
    return (
        "(function(){\n"
        f"  var RID='{run_id}';\n"
        "  var llm=0,ok=0,err=0,ttok=0,ptok=0,ctok=0;\n"
        "  function $e(id){return document.getElementById(id);}\n"
        "  function addChip(row){\n"
        "    try{\n"
        "      var c=JSON.parse(row.getAttribute('data-chip'));\n"
        "      var bar=$e('chips-bar');\n"
        "      if(bar){var s=document.createElement('span');s.className='pipeline-chip';\n"
        "        s.style.borderColor=c.color;s.style.color=c.color;\n"
        "        s.textContent=c.entity+' ✓ '+c.dur;bar.appendChild(s);}\n"
        "      row.removeAttribute('data-chip');\n"
        "    }catch(e){}\n"
        "  }\n"
        "  function upStats(){\n"
        "    var elapsed=Date.now()-(window.__RUN_START_MS__||Date.now());\n"
        "    var tpm=elapsed>60000?Math.round(ttok/(elapsed/60000)):0;\n"
        "    var m={'stat-llm':llm,'stat-ok':ok,'stat-err':err,\n"
        "           'hstat-ttok':ttok.toLocaleString(),'hstat-ptok':ptok.toLocaleString(),'hstat-ctok':ctok.toLocaleString(),\n"
        "           'hstat-tpm':tpm>0?tpm.toLocaleString():'\u2014'};\n"
        "    for(var id in m){var el=$e(id);if(el)el.textContent=m[id];}\n"
        "  }\n"
        "  function setBadgeDone(){\n"
        "    var b=$e('run-status-badge');\n"
        "    if(b){b.className='run-status-badge done';b.innerHTML='<span style=\"font-size:15px\">✓</span><span>COMPLETED</span>';}\n"
        "  }\n"
        "  function processRows(html){\n"
        "    var tb=$e('events-body');\n"
        "    if(!tb||!html)return;\n"
        "    tb.insertAdjacentHTML('afterbegin',html);\n"
        "    tb.querySelectorAll('.json-block:not([data-hl])').forEach(function(b){highlightJSON(b);b.dataset.hl='1';});\n"
        "    tb.querySelectorAll('[data-chip]').forEach(addChip);\n"
        "    var mr=tb.querySelector('[data-mode]');\n"
        "    if(mr){var mm=$e('meta-mode');if(mm)mm.textContent=mr.getAttribute('data-mode');mr.removeAttribute('data-mode');}\n"
        "    updateFilterOptions();\n"
        "    applyFilters();\n"
        "  }\n"
        "  function reverseInitialRows(){\n"
        "    var tb=$e('events-body');\n"
        "    if(!tb)return;\n"
        "    var nodes=Array.from(tb.children);\n"
        "    if(nodes.length<2)return;\n"
        "    var pairs=[];\n"
        "    for(var i=0;i<nodes.length;i+=2){\n"
        "      pairs.push(nodes[i+1]?[nodes[i],nodes[i+1]]:[nodes[i]]);\n"
        "    }\n"
        "    pairs.reverse();\n"
        "    while(tb.firstChild)tb.removeChild(tb.firstChild);\n"
        "    pairs.forEach(function(p){p.forEach(function(r){tb.appendChild(r);});});\n"
        "  }\n"
        "  document.addEventListener('DOMContentLoaded',function(){\n"
        "    reverseInitialRows();\n"
        "    document.querySelectorAll('#events-body [data-chip]').forEach(addChip);\n"
        "    document.querySelectorAll('#events-body .json-block').forEach(function(b){highlightJSON(b);b.dataset.hl='1';});\n"
        "    updateFilterOptions();\n"
        "    if(window.__RUN_DONE__){setBadgeDone();return;}\n"
        "    var sb=window.__INITIAL_BYTES__||0;\n"
        "    var es=new EventSource('/runs/'+RID+'/log-stream?since_bytes='+sb);\n"
        "    es.onmessage=function(ev){\n"
        "      try{\n"
        "        var d=JSON.parse(ev.data);\n"
        "        if(d.html)processRows(d.html);\n"
        "        if(d.stats){llm+=d.stats.llm||0;ok+=d.stats.ok||0;err+=d.stats.err||0;\n"
        "          ttok+=d.stats.ttok||0;ptok+=d.stats.ptok||0;ctok+=d.stats.ctok||0;upStats();}\n"
        "      }catch(ignore){}\n"
        "    };\n"
        "    es.addEventListener('done',function(){\n"
        "      es.close();\n"
        "      setBadgeDone();\n"
        "    });\n"
        "  });\n"
        "})();"
    )


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{height:100%}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#21253a;--border:#2d3147;
  --text:#e2e8f0;--muted:#8892a4;
  --blue:#4a9eff;--green:#34d399;--red:#f87171;
  --purple:#a78bfa;--orange:#fb923c;--gray:#6b7280;--yellow:#fbbf24;
}

/* Scrollbars — dark, thin */
*{scrollbar-width:thin;scrollbar-color:#3a3f5c #0f1117}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#0f1117}
::-webkit-scrollbar-thumb{background:#3a3f5c;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#4e5580}
::-webkit-scrollbar-corner{background:#0f1117}
body{
  background:var(--bg);color:var(--text);
  font-family:'SF Mono','Fira Code','Cascadia Code','Consolas',monospace;
  font-size:12px;line-height:1.6;
  height:100%;display:flex;flex-direction:column;overflow:hidden;
  padding:20px;max-width:1440px;margin:0 auto;
}
a{color:inherit;text-decoration:none}
.mono{font-family:'SF Mono','Fira Code','Consolas',monospace}

/* Header */
.header-card{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:20px 24px;margin-bottom:10px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
}
.header-left{flex:1}
.header-title{
  font-size:15px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  margin-bottom:12px;
}
.header-meta{display:flex;flex-wrap:wrap;gap:24px}
.meta-item{display:flex;flex-direction:column;gap:2px}
.meta-label{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.meta-value{font-size:13px}

/* Header stats panel */
.header-stats{
  display:flex;align-items:center;gap:2px;padding:0 24px;flex-shrink:0;
}
.hstat-item{
  display:flex;flex-direction:column;align-items:center;
  padding:3px 10px;min-width:52px;
}
.hstat-value{font-size:15px;font-weight:700;line-height:1.2}
.hstat-label{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:2px}
.hstat-sep{width:1px;height:26px;background:var(--border);margin:0 4px}

/* Running status badge */
.run-status-badge{
  display:flex;align-items:center;gap:9px;
  padding:9px 20px;border-radius:24px;
  border:1.5px solid var(--green);color:var(--green);
  font-size:11px;font-weight:700;letter-spacing:.1em;white-space:nowrap;
  flex-shrink:0;
  animation:badge-glow 2s ease-in-out infinite;
}
.run-status-badge.done{border-color:var(--muted);color:var(--muted);animation:none}
@keyframes badge-glow{
  0%,100%{box-shadow:0 0 6px rgba(52,211,153,.25)}
  50%{box-shadow:0 0 20px rgba(52,211,153,.65),0 0 40px rgba(52,211,153,.2)}
}
.run-spinner{
  width:13px;height:13px;
  border:2px solid rgba(52,211,153,.2);
  border-top-color:var(--green);
  border-radius:50%;
  animation:spin .75s linear infinite;
  flex-shrink:0;
}
.run-status-badge.done .run-spinner{display:none}
@keyframes spin{to{transform:rotate(360deg)}}

/* Stats bar */
.stats-bar{
  display:flex;align-items:center;flex-wrap:wrap;gap:4px;
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:10px 16px;margin-bottom:10px;
}
.stat-item{
  display:flex;flex-direction:column;align-items:center;
  padding:4px 16px;border-radius:6px;min-width:70px;
}
.stat-value{font-size:20px;font-weight:700;line-height:1.2}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:1px}
.stat-item.success .stat-value{color:var(--green)}
.stat-item.error .stat-value{color:var(--red)}
.stat-sep{width:1px;height:28px;background:var(--border);margin:0 6px}

/* Pipeline chips */
.pipelines-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.pipeline-chip{
  border:1.5px solid;border-radius:20px;padding:3px 14px;
  font-size:12px;font-weight:600;
}

/* Section heading */
.section-heading{
  font-size:10px;text-transform:uppercase;letter-spacing:.12em;
  color:var(--muted);margin-bottom:6px;margin-top:4px;
}

/* Events table */
.table-wrapper{
  overflow-x:auto;overflow-y:auto;border:1px solid var(--border);border-radius:8px;
  flex:1;min-height:0;margin-bottom:20px;
}
table#events-table{width:100%;border-collapse:collapse;font-size:12px}
table#events-table thead{position:sticky;top:0;z-index:10}
table#events-table thead tr{background:var(--surface2)}
table#events-table th{
  padding:9px 12px;text-align:left;font-size:10px;font-weight:600;
  text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
  border-bottom:1px solid var(--border);white-space:nowrap;
}
.event-row{
  cursor:pointer;border-bottom:1px solid var(--border);
  transition:background .1s;
  border-left:3px solid var(--row-color,transparent);
}
.event-row:hover{background:var(--surface2)}
.event-row.row-open{background:var(--surface2)}
.event-row td{padding:7px 12px;vertical-align:middle}
.col-seq{color:var(--muted);width:48px;font-size:11px;white-space:nowrap}
.col-ts{color:var(--muted);white-space:nowrap;font-size:11px}
.col-type{white-space:nowrap}
.col-entity{white-space:nowrap}
.col-prompt{max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.col-model{color:var(--muted);font-size:11px;white-space:nowrap}
.col-dur{color:var(--muted);text-align:right;white-space:nowrap;font-size:11px}

/* Row expand chevron */
.row-chevron{
  display:inline-block;font-size:8px;color:var(--muted);
  margin-right:5px;transition:transform .15s;
}
.event-row.row-open .row-chevron{transform:rotate(90deg)}

/* Type badges */
.type-badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.03em;
}
.ti{font-size:12px}
.type-badge.run             {background:rgba(226,232,240,.12);color:#e2e8f0}
.type-badge.pipeline        {background:rgba(107,114,128,.15);color:#9ca3af}
.type-badge.pipeline-stocks {background:rgba(56,189,248,.15); color:#38bdf8}
.type-badge.pipeline-sectors{background:rgba(167,139,250,.15);color:#a78bfa}
.type-badge.pipeline-ceo    {background:rgba(251,191,36,.15); color:#fbbf24}
.type-badge.llm-req  {background:rgba(74,158,255,.15); color:#4a9eff}
.type-badge.llm-ok   {background:rgba(52,211,153,.15); color:#34d399}
.type-badge.llm-err  {background:rgba(248,113,113,.15);color:#f87171}
.type-badge.srch-req {background:rgba(167,139,250,.15);color:#a78bfa}
.type-badge.srch-resp{background:rgba(251,146,60,.15); color:#fb923c}

.entity-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  margin-right:5px;flex-shrink:0;vertical-align:middle;
}

/* Inline detail rows */
.detail-row>td.detail-cell{
  padding:0;
  border-left:4px solid;
  border-bottom:2px solid var(--border);
  background:var(--surface);
}

.card-meta{
  display:flex;flex-wrap:wrap;gap:0;
  padding:6px 16px;background:rgba(255,255,255,.02);
  border-bottom:1px solid var(--border);
  font-size:11px;color:var(--muted);
}
.card-section{
  padding:10px 16px;border-bottom:1px solid var(--border);
}
.card-section:last-child{border-bottom:none}
.section-label{
  font-size:10px;text-transform:uppercase;letter-spacing:.1em;
  color:var(--muted);margin-bottom:6px;display:flex;align-items:center;gap:8px;
}
.char-count{font-weight:normal;font-size:10px;color:var(--muted)}

.code-block{
  background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:6px;
  padding:10px 14px;font-size:11.5px;line-height:1.55;
  white-space:pre-wrap;word-break:break-word;
  overflow-x:auto;overflow-y:auto;max-height:240px;
  color:var(--text);font-family:'SF Mono','Fira Code','Consolas',monospace;
  margin-top:4px;
}

.copy-btn{
  margin-left:auto;background:none;border:1px solid var(--border);color:var(--muted);
  border-radius:4px;padding:1px 8px;font-size:10px;cursor:pointer;
  font-family:inherit;transition:color .15s,border-color .15s;flex-shrink:0;
}
.copy-btn:hover{color:var(--text);border-color:var(--muted)}
.copy-btn.copied{color:var(--green);border-color:var(--green)}

.error-block{
  background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.3);
  border-radius:6px;padding:10px 14px;color:var(--red);font-size:12px;
}
.token-line{font-size:12px;color:var(--muted)}
.tok-total{color:var(--green)}

.kv-grid{display:flex;flex-direction:column;gap:4px}
.kv-row{display:flex;gap:12px;align-items:baseline}
.kv-key{
  min-width:80px;font-size:11px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.06em;flex-shrink:0;
}
.kv-val{font-size:12px;color:var(--text)}
.kv-val.mono{font-family:'SF Mono','Fira Code','Consolas',monospace;font-size:11px}

.src-list{padding-left:18px}
.src-item{font-size:12px;color:var(--text);padding:2px 0}

/* JSON syntax highlighting */
.json-key   {color:#93c5fd}
.json-str   {color:#86efac}
.json-num   {color:#fcd34d}
.json-bool  {color:#f9a8d4}
.json-null  {color:#9ca3af}

/* Filter dropdowns */
.filter-group{display:flex;gap:12px;margin-left:auto;align-items:flex-end}
.filter-col{display:flex;flex-direction:column;gap:3px;align-items:flex-start}
.filter-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;padding-left:2px}
.filter-dropdown{position:relative}
.filter-btn{
  background:rgba(255,255,255,.06);border:1px solid var(--border);
  color:var(--text);border-radius:6px;padding:5px 12px;
  font-size:11px;cursor:pointer;font-family:inherit;
  white-space:nowrap;display:flex;align-items:center;gap:6px;
  transition:background .15s;
}
.filter-btn:hover{background:rgba(255,255,255,.10)}
.filter-btn.has-filter{border-color:#1976d2;color:#4a9eff}
.filter-panel{
  position:absolute;top:calc(100% + 4px);right:0;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:6px;min-width:140px;z-index:100;padding:4px 0;
  box-shadow:0 4px 16px rgba(0,0,0,.4);
}
#dd-etypes .filter-btn{min-width:170px}
#dd-etypes .filter-panel{min-width:170px}
.filter-opt{
  display:flex;align-items:center;gap:8px;padding:6px 12px;
  cursor:pointer;font-size:12px;color:var(--text);user-select:none;
}
.filter-opt:hover{background:rgba(255,255,255,.06)}
.filter-opt input[type=checkbox]{accent-color:#1976d2;cursor:pointer}
.dd-arrow{font-size:10px;color:var(--muted)}
.clear-filters-btn{
  background:none;border:none;padding:5px 2px;
  font-size:11px;font-family:inherit;cursor:pointer;
  color:var(--blue);letter-spacing:.01em;
  text-decoration:underline;text-underline-offset:2px;
  transition:color .15s,opacity .15s;
}
.clear-filters-btn:hover{color:#74b4ff}
.clear-filters-btn:disabled{color:var(--muted);text-decoration:none;cursor:default;opacity:.45}

/* Pipeline column */
.col-pipeline{white-space:nowrap}
.pipeline-badge{
  display:inline-flex;align-items:center;
  padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.06em;
}
.pipeline-badge-stocks  {background:rgba(56,189,248,.15); color:#38bdf8}
.pipeline-badge-sectors {background:rgba(167,139,250,.15);color:#a78bfa}
.pipeline-badge-ceo     {background:rgba(251,191,36,.15); color:#fbbf24}
.pipeline-badge-empty   {color:var(--muted)}

/* Search query info button */
.srch-info-btn{
  background:none;border:none;color:#a78bfa;cursor:pointer;
  font-size:13px;padding:0 3px 0 5px;vertical-align:middle;
  opacity:.65;line-height:1;border-radius:3px;
  transition:opacity .15s,background .15s;
}
.srch-info-btn:hover{opacity:1;background:rgba(167,139,250,.18)}

/* Search query popup */
.srch-popup{
  position:fixed;z-index:9999;
  background:var(--surface2);border:1px solid rgba(167,139,250,.35);
  border-radius:8px;min-width:280px;max-width:540px;
  box-shadow:0 8px 32px rgba(0,0,0,.55);font-size:12px;
}
.srch-popup-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 12px;border-bottom:1px solid var(--border);
  font-size:11px;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);
}
.srch-copy-btn{
  background:none;border:1px solid var(--border);color:var(--muted);
  border-radius:4px;padding:1px 8px;font-size:10px;cursor:pointer;
  font-family:inherit;transition:color .15s,border-color .15s;
}
.srch-copy-btn:hover{color:var(--text);border-color:var(--muted)}
.srch-copy-btn.copied{color:var(--green);border-color:var(--green)}
.srch-popup-body{
  padding:8px 12px;max-height:300px;overflow-y:auto;
  display:flex;flex-direction:column;gap:6px;
}
.srch-popup-item{display:flex;gap:8px;align-items:flex-start}
.srch-popup-num{
  color:var(--muted);font-size:11px;min-width:18px;
  flex-shrink:0;padding-top:1px;
}
.srch-popup-query{color:var(--text);line-height:1.5;word-break:break-word}
"""


# ── JS (static interactivity — no DOMContentLoaded here) ──────────────────────

_JS = """
var _openSeq = null;

function toggleRow(seq) {
  var detailRow = document.getElementById('detail-row-' + seq);
  var headerRow = document.getElementById('row-' + seq);
  if (!detailRow || !headerRow) return;
  var isOpen = detailRow.style.display !== 'none';
  if (_openSeq !== null && _openSeq !== seq) {
    var prevDetail = document.getElementById('detail-row-' + _openSeq);
    var prevHeader = document.getElementById('row-' + _openSeq);
    if (prevDetail) prevDetail.style.display = 'none';
    if (prevHeader) prevHeader.classList.remove('row-open');
    _openSeq = null;
  }
  if (isOpen) {
    detailRow.style.display = 'none';
    headerRow.classList.remove('row-open');
    _openSeq = null;
  } else {
    detailRow.style.display = 'table-row';
    headerRow.classList.add('row-open');
    _openSeq = seq;
  }
}

function copyBlock(btn) {
  var section = btn.closest('.card-section');
  var pre = section && section.querySelector('pre');
  if (!pre) return;
  var text = pre.textContent;
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = 'copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.innerHTML = '&#x2398; copy'; btn.classList.remove('copied'); }, 1500);
  }).catch(function() {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = 'copied!';
    setTimeout(function() { btn.innerHTML = '&#x2398; copy'; }, 1500);
  });
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

var _openDD = null;

function toggleDropdown(id) {
  var panel = document.getElementById(id + '-panel');
  if (!panel) return;
  if (_openDD && _openDD !== id) {
    var prev = document.getElementById(_openDD + '-panel');
    if (prev) prev.style.display = 'none';
  }
  var isOpen = panel.style.display !== 'none';
  panel.style.display = isOpen ? 'none' : 'block';
  _openDD = isOpen ? null : id;
}

document.addEventListener('click', function(e) {
  if (_openDD && !e.target.closest('.filter-dropdown')) {
    var p = document.getElementById(_openDD + '-panel');
    if (p) p.style.display = 'none';
    _openDD = null;
  }
});

function ensureFilterOption(ddId, value, color) {
  if (!value) return;
  var panel = document.getElementById(ddId + '-panel');
  var safeId = value.replace(/[^a-zA-Z0-9_-]/g, '_');
  var optId = 'fopt-' + ddId + '-' + safeId;
  if (!panel || document.getElementById(optId)) return;
  var lbl = document.createElement('label');
  lbl.className = 'filter-opt';
  lbl.id = optId;
  var cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.value = value;
  cb.addEventListener('change', applyFilters);
  lbl.appendChild(cb);
  if (color) {
    lbl.style.color = color;
  }
  lbl.appendChild(document.createTextNode(' ' + value.toUpperCase()));
  panel.appendChild(lbl);
}

var _PTYPE_COLORS = {'stocks':'#38bdf8','sectors':'#a78bfa','ceo':'#fbbf24'};
var _ETYPE_COLORS = {
  'LLM REQUEST':'#4a9eff','LLM RESPONSE':'#34d399','LLM ERROR':'#f87171',
  'SEARCH REQ':'#a78bfa','SEARCH RESP':'#fb923c',
  'PIPELINE':'#9ca3af','PIPELINE END':'#9ca3af','RUN START':'#e2e8f0','RUN END':'#e2e8f0'
};

function computeRPM() {
  var rows = document.querySelectorAll('#events-body tr.type-llm-req');
  if (!rows.length) return;
  var buckets = {};
  rows.forEach(function(row) {
    var cell = row.querySelector('.col-ts');
    if (!cell) return;
    var key = cell.textContent.trim().substring(0, 5);
    buckets[key] = (buckets[key] || 0) + 1;
  });
  var counts = Object.values(buckets);
  if (!counts.length) return;
  var mn = Math.min.apply(null, counts);
  var mx = Math.max.apply(null, counts);
  var minEl = document.getElementById('hstat-rpm-min');
  var maxEl = document.getElementById('hstat-rpm-max');
  if (minEl) minEl.textContent = mn;
  if (maxEl) maxEl.textContent = mx;
}

function updateFilterOptions() {
  document.querySelectorAll('#events-body .event-row').forEach(function(row) {
    var entity      = row.getAttribute('data-entity');
    var ptype       = row.getAttribute('data-ptype');
    var prompt      = row.getAttribute('data-prompt');
    var etype       = row.getAttribute('data-etype');
    var promptBase  = prompt ? prompt.replace(/ \(round \d+\)$/, '') : '';
    var entityColor = row.style.getPropertyValue('--row-color') || '';
    if (entity)     ensureFilterOption('dd-tickers', entity,     entityColor);
    if (ptype)      ensureFilterOption('dd-types',   ptype,      _PTYPE_COLORS[(ptype||'').toLowerCase()]);
    if (etype)      ensureFilterOption('dd-etypes',  etype,      _ETYPE_COLORS[etype]);
    if (promptBase) ensureFilterOption('dd-prompts', promptBase, '');
  });
  computeRPM();
}

function getFilterSelections(ddId) {
  var panel = document.getElementById(ddId + '-panel');
  if (!panel) return [];
  return Array.prototype.map.call(
    panel.querySelectorAll('input[type=checkbox]:checked'),
    function(cb) { return cb.value; }
  );
}

function updateFilterLabel(ddId, allLabel) {
  var sel  = getFilterSelections(ddId);
  var span = document.getElementById(ddId + '-label');
  var btn  = document.getElementById(ddId + '-btn');
  if (!span || !btn) return;
  if (sel.length === 0) {
    span.textContent = allLabel;
    btn.classList.remove('has-filter');
  } else if (sel.length === 1) {
    span.textContent = sel[0].toUpperCase();
    btn.classList.add('has-filter');
  } else {
    span.textContent = sel.length + ' selected';
    btn.classList.add('has-filter');
  }
}

function clearFilters() {
  ['dd-tickers','dd-types','dd-etypes','dd-prompts'].forEach(function(ddId) {
    var panel = document.getElementById(ddId + '-panel');
    if (panel) panel.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
  });
  applyFilters();
}

function applyFilters() {
  updateFilterLabel('dd-tickers', 'All Tickers');
  updateFilterLabel('dd-types',   'All Types');
  updateFilterLabel('dd-etypes',  'All Event Types');
  updateFilterLabel('dd-prompts', 'All Prompts');
  var selTickers = getFilterSelections('dd-tickers');
  var selTypes   = getFilterSelections('dd-types');
  var selEtypes  = getFilterSelections('dd-etypes');
  var selPrompts = getFilterSelections('dd-prompts');
  var hasAny = selTickers.length + selTypes.length + selEtypes.length + selPrompts.length > 0;
  var clearBtn = document.getElementById('clear-filters-btn');
  if (clearBtn) clearBtn.disabled = !hasAny;
  document.querySelectorAll('#events-body .event-row').forEach(function(row) {
    var entity     = row.getAttribute('data-entity') || '';
    var ptype      = row.getAttribute('data-ptype')  || '';
    var prompt     = row.getAttribute('data-prompt')  || '';
    var etype      = row.getAttribute('data-etype')  || '';
    var promptBase = prompt.replace(/ \(round \d+\)$/, '');
    var seq        = row.id.replace('row-', '');
    var detail     = document.getElementById('detail-row-' + seq);
    if (!entity && !ptype && !prompt && !etype) { row.style.display = ''; return; }
    var pass = (selTickers.length === 0 || selTickers.indexOf(entity)     !== -1) &&
               (selTypes.length   === 0 || selTypes.indexOf(ptype)        !== -1) &&
               (selEtypes.length  === 0 || selEtypes.indexOf(etype)       !== -1) &&
               (selPrompts.length === 0 || selPrompts.indexOf(promptBase) !== -1);
    row.style.display = pass ? '' : 'none';
    if (!pass) {
      if (detail) detail.style.display = 'none';
      if (String(_openSeq) === seq) { row.classList.remove('row-open'); _openSeq = null; }
    }
  });
}

var _srchPopup = null;
var _srchHideTimer = null;

function showSearchPopup(btn, seq) {
  clearTimeout(_srchHideTimer);
  if (_srchPopup) { _srchPopup.remove(); _srchPopup = null; }

  var row = document.getElementById('row-' + seq);
  if (!row) return;
  var entity = row.getAttribute('data-entity');

  var queries = [];
  document.querySelectorAll('#events-body tr.event-row').forEach(function(r) {
    var rseq = parseInt(r.id.replace('row-', ''), 10);
    var q = r.getAttribute('data-search-query');
    if (q && r.getAttribute('data-entity') === entity && rseq <= seq) {
      queries.push({ seq: rseq, query: q });
    }
  });
  queries.sort(function(a, b) { return a.seq - b.seq; });
  if (!queries.length) return;

  var allText = queries.map(function(q) { return q.query; }).join('\\n\\n');

  var popup = document.createElement('div');
  popup.className = 'srch-popup';

  var hdr = document.createElement('div');
  hdr.className = 'srch-popup-header';
  hdr.appendChild(document.createTextNode('Search Queries (' + queries.length + ')'));
  var cb = document.createElement('button');
  cb.className = 'srch-copy-btn';
  cb.innerHTML = '&#x2398; copy';
  cb.addEventListener('click', function(e) {
    e.stopPropagation();
    navigator.clipboard.writeText(allText).then(function() {
      cb.textContent = 'copied!';
      cb.classList.add('copied');
      setTimeout(function() { cb.innerHTML = '&#x2398; copy'; cb.classList.remove('copied'); }, 1500);
    });
  });
  hdr.appendChild(cb);
  popup.appendChild(hdr);

  var body = document.createElement('div');
  body.className = 'srch-popup-body';
  queries.forEach(function(q, i) {
    var item = document.createElement('div');
    item.className = 'srch-popup-item';
    var num = document.createElement('span');
    num.className = 'srch-popup-num';
    num.textContent = (i + 1) + '.';
    var qs = document.createElement('span');
    qs.className = 'srch-popup-query';
    qs.textContent = q.query;
    item.appendChild(num);
    item.appendChild(qs);
    body.appendChild(item);
  });
  popup.appendChild(body);

  document.body.appendChild(popup);
  var rect = btn.getBoundingClientRect();
  var popW = popup.offsetWidth || 300;
  var popH = popup.offsetHeight || 200;

  // Horizontal: center on button, clamp to viewport edges
  var left = rect.left - popW / 2 + 12;
  if (left < 8) left = 8;
  if (left + popW > window.innerWidth - 8) left = window.innerWidth - popW - 8;

  // Vertical: prefer above; fall back to below or clamp if neither fits
  var spaceAbove = rect.top - 8;
  var spaceBelow = window.innerHeight - rect.bottom - 8;
  var top;
  if (popH <= spaceAbove) {
    top = rect.top - popH - 6;
  } else if (spaceBelow >= spaceAbove) {
    top = rect.bottom + 6;
    if (top + popH > window.innerHeight - 8) top = window.innerHeight - popH - 8;
  } else {
    top = 8;
  }
  popup.style.top = top + 'px';
  popup.style.left = left + 'px';

  popup.addEventListener('mouseenter', function() { clearTimeout(_srchHideTimer); });
  popup.addEventListener('mouseleave', function() { scheduleHideSearchPopup(); });
  _srchPopup = popup;
}

function scheduleHideSearchPopup() {
  _srchHideTimer = setTimeout(function() {
    if (_srchPopup) { _srchPopup.remove(); _srchPopup = null; }
  }, 200);
}

function highlightJSON(el) {
  var raw = el.textContent;
  var parsed;
  try { parsed = JSON.parse(raw); } catch(e) { return; }
  var fmt = JSON.stringify(parsed, null, 2);
  el.innerHTML = fmt.replace(
    /("(?:\\\\u[0-9a-fA-F]{4}|\\\\[^u]|[^\\\\"])*"(?=\\s*:)|"(?:\\\\u[0-9a-fA-F]{4}|\\\\[^u]|[^\\\\"])*"|-?\\d+(?:\\.\\d+)?(?:[eE][+\\-]?\\d+)?|true|false|null)/g,
    function(m) {
      var cls;
      if (m[0] === '"') {
        cls = /^".*":?$/.test(m) && m[m.length-1] === ':' ? 'json-key' : 'json-str';
        if (cls === 'json-key') m = m.slice(0,-0);
      } else if (m === 'true' || m === 'false') { cls = 'json-bool';
      } else if (m === 'null') { cls = 'json-null';
      } else { cls = 'json-num'; }
      return '<span class="' + cls + '">' + esc(m) + '</span>';
    }
  );
}
"""
