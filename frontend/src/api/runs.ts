import type { Run } from '../types/run'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/runs`

export async function createRun(
  modelIds: string[],
  name: string,
  tickers: Record<string, unknown>[],
  candleFrequency: string = '1d',
  enrichmentEnabled: boolean = true,
): Promise<Run> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_ids: modelIds,
      name,
      tickers,
      candle_frequency: candleFrequency,
      enrichment_enabled: enrichmentEnabled,
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

export async function enrichPreview(
  tickers: Record<string, unknown>[],
  candleFrequency: string = '1d',
): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${BASE}/enrich-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, candle_frequency: candleFrequency }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Enrichment failed: ${res.statusText}`)
  }
  return res.json()
}

export async function stopRun(id: string): Promise<Run> {
  const res = await fetch(`${BASE}/${id}/stop`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to stop run: ${res.statusText}`)
  }
  return res.json()
}
