export interface Run {
  id: string
  status: 'fetching' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  name: string | null
  created_at: string
  completed_at: string | null
  error: string | null
  output_dir: string | null
  model_names: string[] | null
  ticker_count: number | null
  ibk_session_id: string | null
}
