from __future__ import annotations

import asyncio
import html as _html_mod
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles


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


# ── RunLogger ──────────────────────────────────────────────────────────────────

class RunLogger:
    """Buffers run events in memory and writes a single self-contained HTML log at close()."""

    def __init__(self, log_path: str) -> None:
        self._path = log_path
        self._lock = asyncio.Lock()
        self._events: list[_Event] = []
        self._seq: int = 0
        self._run_meta: dict[str, str] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def open(self, run_id: str, started_at: str) -> None:
        async with self._lock:
            self._run_meta = {"run_id": run_id, "started_at": started_at}

    async def close(self) -> None:
        content = self._render_html()
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._path, "w", encoding="utf-8") as f:
            await f.write(content)

    # ── Run-level events ───────────────────────────────────────────────────────

    async def run_start(
        self,
        *,
        mode: str,
        models: list[str],
        tickers: list[str],
        agent_prompts: list[str],
        sector_prompts: list[str],
    ) -> None:
        async with self._lock:
            self._seq += 1
            self._events.append(_Event(
                seq=self._seq, ts=_ts(), type="run_start",
                pipeline_type="", entity="", model="", pipeline_id="",
                agent_id="", prompt_title="", status="started", duration_ms=-1,
                payload={
                    "mode": mode, "models": models, "tickers": tickers,
                    "agent_prompts": agent_prompts, "sector_prompts": sector_prompts,
                },
            ))

    async def run_end(self, *, total_duration_ms: int) -> None:
        async with self._lock:
            self._seq += 1
            self._events.append(_Event(
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
            self._events.append(_Event(
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
            self._events.append(_Event(
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
            self._events.append(_Event(
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
            self._events.append(_Event(
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
        async with self._lock:
            self._seq += 1
            self._events.append(_Event(
                seq=self._seq, ts=_ts(), type="llm_request",
                pipeline_type=pipeline_type, entity=entity, model=model,
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="", duration_ms=-1,
                payload={
                    "system_prompt": system_prompt,
                    "user_message": user_message,
                },
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
        async with self._lock:
            self._seq += 1
            self._events.append(_Event(
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
        async with self._lock:
            self._seq += 1
            self._events.append(_Event(
                seq=self._seq, ts=_ts(), type="llm_response_error",
                pipeline_type=pipeline_type, entity=entity, model="",
                pipeline_id=pipeline_id, agent_id=agent_id,
                prompt_title=prompt_title, status="error", duration_ms=duration_ms,
                payload={"error": error},
            ))

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _compute_stats(self) -> dict[str, Any]:
        ok = [e for e in self._events if e.type == "llm_response_ok"]
        err = [e for e in self._events if e.type == "llm_response_error"]
        pt = sum(e.payload.get("tokens", {}).get("prompt_tokens", 0) for e in ok)
        ct = sum(e.payload.get("tokens", {}).get("completion_tokens", 0) for e in ok)
        tt = sum(e.payload.get("tokens", {}).get("total_tokens", 0) for e in ok)
        return {
            "llm_calls": len(ok) + len(err),
            "llm_success": len(ok),
            "llm_errors": len(err),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
        }

    def _render_html(self) -> str:
        run_id = self._run_meta.get("run_id", "—")
        started_at = self._run_meta.get("started_at", "—")
        stats = self._compute_stats()

        # Resolve entity for every event (use pipeline_id → entity lookup as fallback)
        pid_entity: dict[str, str] = {
            e.pipeline_id: e.entity
            for e in self._events
            if e.type == "pipeline_start" and e.pipeline_id and e.entity
        }
        seq_entity: dict[int, str] = {
            e.seq: e.entity or pid_entity.get(e.pipeline_id, "")
            for e in self._events
        }

        # Assign a color to each unique entity in order of first appearance
        entity_colors: dict[str, str] = {}
        for entity in seq_entity.values():
            if entity and entity not in entity_colors:
                entity_colors[entity] = _ENTITY_COLORS[len(entity_colors) % len(_ENTITY_COLORS)]

        # Run metadata
        run_end_events = [e for e in self._events if e.type == "run_end"]
        total_ms = run_end_events[-1].payload.get("total_duration_ms", 0) if run_end_events else 0
        total_dur = _fmt_duration(total_ms) if total_ms else "—"

        run_start_events = [e for e in self._events if e.type == "run_start"]
        run_payload = run_start_events[0].payload if run_start_events else {}

        # Build sections
        chips_html = _render_chips(self._events, entity_colors, seq_entity)
        table_rows_list: list[str] = []
        for e in self._events:
            table_rows_list.append(_render_row(e, entity_colors, seq_entity))
            table_rows_list.append(_render_inline_detail(e, entity_colors, seq_entity))
        table_rows = "\n".join(table_rows_list)

        run_id_short = run_id[:8] if len(run_id) > 8 else run_id

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Run Log — {_h(run_id_short)}</title>
<style>{_CSS}</style>
</head>
<body>

<div class="header-card">
  <div class="header-title">STOCK-AGENTS &middot; RUN LOG</div>
  <div class="header-meta">
    <span class="meta-item"><span class="meta-label">Run ID</span><span class="meta-value mono">{_h(run_id)}</span></span>
    <span class="meta-item"><span class="meta-label">Started</span><span class="meta-value">{_h(started_at)}</span></span>
    <span class="meta-item"><span class="meta-label">Duration</span><span class="meta-value">{total_dur}</span></span>
    <span class="meta-item"><span class="meta-label">Mode</span><span class="meta-value">{_h(run_payload.get("mode", "—"))}</span></span>
  </div>
</div>

<div class="stats-bar">
  <div class="stat-item"><span class="stat-value">{stats["llm_calls"]}</span><span class="stat-label">LLM Calls</span></div>
  <div class="stat-item success"><span class="stat-value">{stats["llm_success"]}</span><span class="stat-label">Success</span></div>
  <div class="stat-item error"><span class="stat-value">{stats["llm_errors"]}</span><span class="stat-label">Errors</span></div>
  <div class="stat-sep"></div>
  <div class="stat-item"><span class="stat-value">{stats["total_tokens"]:,}</span><span class="stat-label">Total Tokens</span></div>
  <div class="stat-item"><span class="stat-value">{stats["prompt_tokens"]:,}</span><span class="stat-label">Prompt</span></div>
  <div class="stat-item"><span class="stat-value">{stats["completion_tokens"]:,}</span><span class="stat-label">Completion</span></div>
</div>

{chips_html}

<div class="section-heading" id="events-table-anchor">Events</div>
<div class="table-wrapper">
<table id="events-table">
  <thead>
    <tr>
      <th>#</th><th>Time</th><th>Type</th><th>Entity</th>
      <th>Prompt / Detail</th><th>Model</th><th>Duration</th>
    </tr>
  </thead>
  <tbody>
{table_rows}
  </tbody>
</table>
</div>

<script>{_JS}</script>
</body>
</html>"""


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

def _render_chips(
    events: list[_Event],
    entity_colors: dict[str, str],
    seq_entity: dict[int, str],
) -> str:
    ends = [e for e in events if e.type == "pipeline_end"]
    if not ends:
        return ""
    chips = []
    for e in ends:
        entity = seq_entity.get(e.seq, e.entity)
        color = entity_colors.get(entity, "#6b7280")
        dur = _fmt_duration(e.payload.get("duration_ms", e.duration_ms))
        chips.append(
            f'<span class="pipeline-chip" style="border-color:{color};color:{color}">'
            f'{_h(entity)} &#x2713; {dur}'
            f'</span>'
        )
    return f'<div class="pipelines-bar">{"".join(chips)}</div>'


def _render_row(
    e: _Event,
    entity_colors: dict[str, str],
    seq_entity: dict[int, str],
) -> str:
    icon, css_cls, label = _TYPE_META.get(e.type, ("?", "unknown", e.type.upper()))
    entity = seq_entity.get(e.seq, e.entity)
    color = entity_colors.get(entity, "#6b7280")
    dur = _fmt_duration(e.duration_ms)
    model_disp = _h(_model_short(e.model)) if e.model else "—"
    entity_disp = _h(entity) if entity else "—"
    prompt_disp = _h(e.prompt_title) if e.prompt_title else "—"

    return (
        f'    <tr id="row-{e.seq}" class="event-row type-{css_cls}"'
        f' style="--row-color:{color}" onclick="toggleRow({e.seq})">'
        f'<td class="col-seq"><span class="row-chevron">&#x25B6;</span>{e.seq}</td>'
        f'<td class="col-ts">{_h(e.ts)}</td>'
        f'<td class="col-type"><span class="type-badge {css_cls}">'
        f'<span class="ti">{icon}</span>{label}</span></td>'
        f'<td class="col-entity"><span class="entity-dot" style="background:{color}"></span>'
        f'{entity_disp}</td>'
        f'<td class="col-prompt">{prompt_disp}</td>'
        f'<td class="col-model">{model_disp}</td>'
        f'<td class="col-dur">{dur}</td>'
        f'</tr>'
    )


def _render_inline_detail(
    e: _Event,
    entity_colors: dict[str, str],
    seq_entity: dict[int, str],
) -> str:
    """Collapsed <tr> rendered immediately after its event row; expands on click."""
    entity = seq_entity.get(e.seq, e.entity)
    color = entity_colors.get(entity, "#6b7280")

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
        f'<td colspan="7" class="detail-cell" style="border-left-color:{color}">'
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


def _section_kv(
    pairs: list[tuple[str, str]],
    mono_val: bool = False,
) -> str:
    rows = "".join(
        f'<div class="kv-row">'
        f'<span class="kv-key">{_h(k)}</span>'
        f'<span class="kv-val{"  mono" if mono_val else ""}">{_h(v)}</span>'
        f'</div>'
        for k, v in pairs
    )
    return f'<div class="card-section"><div class="kv-grid">{rows}</div></div>'


def _body_llm_request(p: dict[str, Any]) -> str:
    sys_prompt = p.get("system_prompt", "")
    user_msg = p.get("user_message", "")

    char_note = f' <span class="char-count">({len(sys_prompt):,} chars)</span>' if sys_prompt else ""

    user_display = _pretty_json(user_msg)
    user_is_json = _is_json(user_msg)
    user_block_cls = f'code-block{"  json-block" if user_is_json else ""}'

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
    is_json = _is_json(resp)
    resp_cls = f'code-block{"  json-block" if is_json else ""}'
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


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#21253a;--border:#2d3147;
  --text:#e2e8f0;--muted:#8892a4;
  --blue:#4a9eff;--green:#34d399;--red:#f87171;
  --purple:#a78bfa;--orange:#fb923c;--gray:#6b7280;--yellow:#fbbf24;
}
body{
  background:var(--bg);color:var(--text);
  font-family:'SF Mono','Fira Code','Cascadia Code','Consolas',monospace;
  font-size:12px;line-height:1.6;padding:20px;max-width:1440px;margin:0 auto;
}
a{color:inherit;text-decoration:none}
.mono{font-family:'SF Mono','Fira Code','Consolas',monospace}

/* Header */
.header-card{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:20px 24px;margin-bottom:10px;
}
.header-title{
  font-size:15px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  margin-bottom:12px;
}
.header-meta{display:flex;flex-wrap:wrap;gap:24px}
.meta-item{display:flex;flex-direction:column;gap:2px}
.meta-label{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.meta-value{font-size:13px}

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
  overflow-x:auto;border:1px solid var(--border);border-radius:8px;
  margin-bottom:28px;
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
.type-badge.run      {background:rgba(226,232,240,.12);color:#e2e8f0}
.type-badge.pipeline {background:rgba(107,114,128,.15);color:#9ca3af}
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
"""


# ── JS ─────────────────────────────────────────────────────────────────────────

_JS = """
var _openSeq = null;

function toggleRow(seq) {
  var detailRow = document.getElementById('detail-row-' + seq);
  var headerRow = document.getElementById('row-' + seq);
  if (!detailRow || !headerRow) return;

  var isOpen = detailRow.style.display !== 'none';

  // Close the currently open row if it's a different one
  if (_openSeq !== null && _openSeq !== seq) {
    var prevDetail = document.getElementById('detail-row-' + _openSeq);
    var prevHeader = document.getElementById('row-' + _openSeq);
    if (prevDetail) prevDetail.style.display = 'none';
    if (prevHeader) prevHeader.classList.remove('row-open');
    _openSeq = null;
  }

  // Toggle the clicked row
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
    setTimeout(function() {
      btn.innerHTML = '&#x2398; copy';
      btn.classList.remove('copied');
    }, 1500);
  }).catch(function() {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = 'copied!';
    setTimeout(function() { btn.innerHTML = '&#x2398; copy'; }, 1500);
  });
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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
      } else if (m === 'true' || m === 'false') {
        cls = 'json-bool';
      } else if (m === 'null') {
        cls = 'json-null';
      } else {
        cls = 'json-num';
      }
      return '<span class="' + cls + '">' + esc(m) + '</span>';
    }
  );
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.json-block').forEach(highlightJSON);
});
"""
