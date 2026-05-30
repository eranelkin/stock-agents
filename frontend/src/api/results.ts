import type { TickerResult } from '../types/result'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'

export async function fetchResults(runId: string): Promise<TickerResult[]> {
  const res = await fetch(`${BACKEND}/results/${runId}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to fetch results: ${res.statusText}`)
  }
  return res.json()
}
