import type { Run } from '../types/run'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/runs`

export async function triggerScreener(
  mode: 'screener' | 'screener-only-pull' | 'merged',
  modelIds: string[] = [],
): Promise<{ session_id: string }> {
  const res = await fetch(`${BACKEND}/screener/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, model_ids: modelIds }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to trigger screener: ${res.statusText}`)
  }
  return res.json()
}

export async function stopScreener(sessionId: string): Promise<void> {
  const res = await fetch(`${BACKEND}/screener/stop/${sessionId}`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to stop screener: ${res.statusText}`)
  }
}

export async function pollScreenerDone(
  sessionId: string,
  onDone: () => void,
  intervalMs = 2000,
  maxWaitMs = 20 * 60 * 1000,
): Promise<void> {
  const started = Date.now()
  const tick = async () => {
    if (Date.now() - started > maxWaitMs) { onDone(); return }
    try {
      const res = await fetch(`${BACKEND}/screener/log-rows/${sessionId}?since=0`)
      if (res.ok) {
        const data = await res.json()
        if (data.done) { onDone(); return }
      }
    } catch { /* ignore network errors, keep polling */ }
    setTimeout(tick, intervalMs)
  }
  setTimeout(tick, intervalMs)
}

export async function createRun(
  modelIds: string[],
  name: string,
  tickers: Record<string, unknown>[],
): Promise<Run> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_ids: modelIds,
      name,
      tickers,
    }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to start run: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchRun(id: string): Promise<Run> {
  const res = await fetch(`${BASE}/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch run: ${res.statusText}`)
  return res.json()
}

export async function fetchRuns(): Promise<Run[]> {
  const res = await fetch(BASE)
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.statusText}`)
  return res.json()
}

export async function deleteRun(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete run: ${res.statusText}`)
}

export async function deleteRuns(ids: string[]): Promise<void> {
  const res = await fetch(`${BASE}/bulk`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_ids: ids }),
  })
  if (!res.ok) throw new Error(`Failed to delete runs: ${res.statusText}`)
}

export async function stopRun(id: string): Promise<Run> {
  const res = await fetch(`${BASE}/${id}/stop`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to stop run: ${res.statusText}`)
  }
  return res.json()
}
