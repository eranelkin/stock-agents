import type { ScanResult } from '../types/scan'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'

export async function runScan(runId: string): Promise<ScanResult[]> {
  const res = await fetch(`${BACKEND}/analytics/${runId}/scan`, { method: 'POST' })
  if (!res.ok) throw new Error(`Scan failed: ${res.statusText}`)
  return res.json()
}

export async function fetchScanResults(runId: string): Promise<ScanResult[]> {
  const res = await fetch(`${BACKEND}/analytics/${runId}/scan`)
  if (!res.ok) throw new Error(`Failed to load scan results: ${res.statusText}`)
  return res.json()
}
