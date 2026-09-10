from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from backend.config import settings

router = APIRouter(prefix="/market-data", tags=["market-data"])

_sessions: dict[str, dict] = {}
_SESSION_TTL = 3600


def _prune_sessions() -> None:
    now = time.time()
    expired = [k for k, v in _sessions.items() if now - v["created_at"] > _SESSION_TTL]
    for k in expired:
        del _sessions[k]


async def _run_subprocess(session_id: str, cmd: list[str], cwd: str) -> None:
    session = _sessions[session_id]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        session["proc"] = proc
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            session["lines"].append(line)
        await proc.wait()
        session["return_code"] = proc.returncode
    except Exception as exc:
        session["lines"].append(f"[ERROR] Subprocess failed: {exc}")
    finally:
        session["proc"] = None
        session["done"] = True


@router.post("/trigger", status_code=202)
async def trigger_market_data(background_tasks: BackgroundTasks) -> JSONResponse:
    """Spawn the market-data CLI subprocess and return a session_id for log tracking."""
    _prune_sessions()

    python = settings.market_data_python
    base_path = Path(settings.market_data_path).resolve()
    main_py = str(base_path / "main.py")

    cmd = [python, "-u", main_py]

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "lines": [],
        "done": False,
        "return_code": None,
        "created_at": time.time(),
        "proc": None,
    }

    background_tasks.add_task(_run_subprocess, session_id, cmd, str(base_path))
    return JSONResponse({"session_id": session_id}, status_code=202)


@router.post("/stop/{session_id}", status_code=200)
async def stop_market_data(session_id: str) -> dict:
    """Kill the running market-data subprocess."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    proc = session.get("proc")
    if proc is not None:
        try:
            proc.terminate()
            await asyncio.sleep(0.5)
            if proc.returncode is None:
                proc.kill()
        except ProcessLookupError:
            pass
        session["lines"].append("[STOPPED] Run was stopped by user.")
        session["done"] = True
        session["proc"] = None

    return {"stopped": True}


_LOG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market Data Log</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0f1117;--surface:#1a1d27;--border:#2d3147;
  --text:#e2e8f0;--muted:#8892a4;
  --green:#34d399;--red:#f87171;--blue:#4a9eff;--yellow:#fbbf24;
}}
body{{
  background:var(--bg);color:var(--text);
  font-family:'SF Mono','Fira Code','Cascadia Code','Consolas',monospace;
  font-size:12px;line-height:1.6;padding:20px;max-width:1440px;margin:0 auto;
}}
.header{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:16px 20px;margin-bottom:12px;display:flex;align-items:center;gap:12px;
}}
.header-title{{font-size:14px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}}
.mode-chip{{
  font-size:11px;font-weight:600;padding:2px 10px;border-radius:12px;
  border:1px solid var(--blue);color:var(--blue);
}}
.status-chip{{
  font-size:11px;font-weight:600;padding:2px 10px;border-radius:12px;margin-left:auto;
}}
.status-chip.running{{border:1px solid var(--yellow);color:var(--yellow)}}
.status-chip.done{{border:1px solid var(--green);color:var(--green)}}
.status-chip.error{{border:1px solid var(--red);color:var(--red)}}
#log{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:16px;overflow-y:auto;min-height:200px;
}}
.line{{padding:1px 0;white-space:pre-wrap;word-break:break-all}}
.line.err{{color:var(--red)}}
.line.warn{{color:var(--yellow)}}
.line.info{{color:var(--text)}}
</style>
</head>
<body>
<div class="header">
  <span class="header-title">Market Data Log</span>
  <span class="mode-chip">Alpha Vantage</span>
  <span id="status-chip" class="status-chip running">Running…</span>
</div>
<div id="log">{initial_lines}</div>
<script>
var since = {initial_count};
var done = {done_flag};
var sessionId = "{session_id}";

function classify(line) {{
  var l = line.toLowerCase();
  if (l.includes('error') || l.includes('exception') || l.startsWith('[error]')) return 'err';
  if (l.includes('warn')) return 'warn';
  return 'info';
}}

function appendLines(lines) {{
  var log = document.getElementById('log');
  var atBottom = log.scrollHeight - log.scrollTop <= log.clientHeight + 40;
  lines.forEach(function(line) {{
    var div = document.createElement('div');
    div.className = 'line ' + classify(line);
    div.textContent = line;
    log.appendChild(div);
  }});
  if (atBottom) log.scrollTop = log.scrollHeight;
}}

function setDone(returnCode) {{
  var chip = document.getElementById('status-chip');
  if (returnCode === 0 || returnCode === null) {{
    chip.textContent = 'Done';
    chip.className = 'status-chip done';
  }} else {{
    chip.textContent = 'Failed (exit ' + returnCode + ')';
    chip.className = 'status-chip error';
  }}
}}

function poll() {{
  if (done) return;
  fetch('/market-data/log-rows/{session_id}?since=' + since)
    .then(function(r) {{
      if (r.status === 404) {{
        done = true;
        var chip = document.getElementById('status-chip');
        chip.textContent = 'Session expired (backend restarted)';
        chip.className = 'status-chip done';
        return null;
      }}
      return r.json();
    }})
    .then(function(data) {{
      if (!data) return;
      if (data.lines && data.lines.length > 0) {{
        appendLines(data.lines);
        since += data.lines.length;
      }}
      if (data.done) {{
        done = true;
        setDone(data.return_code);
        return;
      }}
      setTimeout(poll, 500);
    }})
    .catch(function() {{ setTimeout(poll, 2000); }});
}}

if (!done) setTimeout(poll, 500);
else setDone(null);
</script>
</body>
</html>
"""


@router.get("/log/{session_id}", response_class=HTMLResponse)
async def get_market_data_log(session_id: str) -> HTMLResponse:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    initial_lines = "\n".join(
        f'<div class="line {_classify(l)}">{_escape(l)}</div>'
        for l in session["lines"]
    )
    done_flag = "true" if session["done"] else "false"

    html = _LOG_HTML.format(
        session_id=session_id,
        initial_lines=initial_lines,
        initial_count=len(session["lines"]),
        done_flag=done_flag,
    )
    return HTMLResponse(content=html)


@router.get("/log-rows/{session_id}")
async def get_market_data_log_rows(session_id: str, since: int = 0) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    return {
        "lines": session["lines"][since:],
        "total": len(session["lines"]),
        "done": session["done"],
        "return_code": session["return_code"],
    }


def _classify(line: str) -> str:
    lower = line.lower()
    if "error" in lower or "exception" in lower or lower.startswith("[error]"):
        return "err"
    if "warn" in lower:
        return "warn"
    return "info"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
