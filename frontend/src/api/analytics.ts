import type { Run } from '../types/run'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'

export async function fetchAnalyticsRuns(): Promise<Run[]> {
  const res = await fetch(`${BACKEND}/analytics`)
  if (!res.ok) throw new Error(`Failed to load analytics: ${res.statusText}`)
  return res.json()
}
