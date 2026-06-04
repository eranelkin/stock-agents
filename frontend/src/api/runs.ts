import type { Run } from '../types/run'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/runs`

export async function createRun(
  modelIds: string[],
  name: string,
  tickers: Record<string, unknown>[],
): Promise<Run> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_ids: modelIds, name, tickers }),
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

export async function stopRun(id: string): Promise<Run> {
  const res = await fetch(`${BASE}/${id}/stop`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to stop run: ${res.statusText}`)
  }
  return res.json()
}
