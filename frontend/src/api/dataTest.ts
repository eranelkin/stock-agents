import type { DataTestField, DataTestResult } from '../types/dataTest'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/data-test`

export async function fetchDataTestFields(): Promise<DataTestField[]> {
  const res = await fetch(`${BASE}/fields`)
  if (!res.ok) throw new Error(`Failed to fetch fields: ${res.statusText}`)
  return res.json()
}

export async function runDataTest(symbols: string[]): Promise<DataTestResult> {
  const res = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbols }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Data test failed: ${res.statusText}`)
  }
  return res.json()
}
