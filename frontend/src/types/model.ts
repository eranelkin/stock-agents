export interface Model {
  id: string
  name: string
  model_id: string
  provider: string
  base_url: string | null
  api_key_configured: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ModelCreatePayload {
  name: string
  model_id: string
  provider: string
  base_url: string | null
  api_key: string | null
}

export interface ModelUpdatePayload {
  name?: string
  model_id?: string
  provider?: string
  base_url?: string | null
  api_key?: string | null
}
