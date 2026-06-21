import type { Prompt } from '../types/prompt'

const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
const BASE = `${BACKEND}/prompts`

export async function fetchPrompts(category?: string): Promise<Prompt[]> {
  const url = category ? `${BASE}?category=${encodeURIComponent(category)}` : BASE
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch prompts: ${res.statusText}`)
  return res.json()
}

/** Fetch all active agent prompts — used to compute CEO input schema in the UI. */
export async function fetchActiveAgentPrompts(): Promise<Prompt[]> {
  const res = await fetch(`${BASE}?category=agents`)
  if (!res.ok) throw new Error(`Failed to fetch agent prompts: ${res.statusText}`)
  const all: Prompt[] = await res.json()
  return all.filter((p) => p.is_active)
}

export async function createPrompt(payload: {
  title: string
  content: string
  category: string
  search_mode?: string | null
  search_enabled?: boolean
  search_query_template?: string | null
  output_schema?: Record<string, unknown> | null
}): Promise<Prompt> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to create prompt: ${res.statusText}`)
  }
  return res.json()
}

export async function updatePrompt(
  id: string,
  payload: Partial<{
    title: string
    content: string
    category: string
    search_mode: string | null
    search_enabled: boolean
    search_query_template: string | null
    output_schema: Record<string, unknown> | null
  }>,
): Promise<Prompt> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Failed to update prompt: ${res.statusText}`)
  }
  return res.json()
}

export async function togglePromptActive(id: string, is_active: boolean): Promise<Prompt> {
  const res = await fetch(`${BASE}/${id}/active`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active }),
  })
  if (!res.ok) throw new Error(`Failed to toggle prompt: ${res.statusText}`)
  return res.json()
}

export async function deletePrompt(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete prompt: ${res.statusText}`)
}
