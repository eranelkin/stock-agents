import type { Model, ModelCreatePayload, ModelUpdatePayload } from '../types/model'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/models`

export async function fetchModels(active?: boolean): Promise<Model[]> {
  const url = active !== undefined ? `${BASE}?active=${active}` : BASE
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.statusText}`)
  return res.json()
}

export async function createModel(payload: ModelCreatePayload): Promise<Model> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to create model: ${res.statusText}`)
  return res.json()
}

export async function updateModel(id: string, payload: ModelUpdatePayload): Promise<Model> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to update model: ${res.statusText}`)
  return res.json()
}

export async function toggleModelActive(id: string, is_active: boolean): Promise<Model> {
  const res = await fetch(`${BASE}/${id}/active`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active }),
  })
  if (!res.ok) throw new Error(`Failed to toggle model: ${res.statusText}`)
  return res.json()
}

export async function deleteModel(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete model: ${res.statusText}`)
}
