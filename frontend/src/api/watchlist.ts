import type { WatchlistEntry, WatchlistEntryPayload } from '../types/watchlist'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/watchlist`

export async function fetchWatchlist(env: 'prod' | 'test' = 'prod'): Promise<WatchlistEntry[]> {
  const res = await fetch(`${BASE}?env=${env}`)
  if (!res.ok) throw new Error(`Failed to fetch watchlist: ${res.statusText}`)
  return res.json()
}

export async function addWatchlistEntry(
  payload: WatchlistEntryPayload,
  env: 'prod' | 'test' = 'prod',
): Promise<WatchlistEntry> {
  const res = await fetch(`${BASE}?env=${env}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to add symbol: ${res.statusText}`)
  }
  return res.json()
}

export async function updateWatchlistEntry(
  symbol: string,
  payload: WatchlistEntryPayload,
  env: 'prod' | 'test' = 'prod',
): Promise<WatchlistEntry> {
  const res = await fetch(`${BASE}/${symbol}?env=${env}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to update symbol: ${res.statusText}`)
  }
  return res.json()
}

export async function deleteWatchlistEntry(symbol: string, env: 'prod' | 'test' = 'prod'): Promise<void> {
  const res = await fetch(`${BASE}/${symbol}?env=${env}`, { method: 'DELETE' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to delete symbol: ${res.statusText}`)
  }
}
