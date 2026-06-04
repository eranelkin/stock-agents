export interface Run {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  name: string | null
  created_at: string
  completed_at: string | null
  error: string | null
  output_dir: string | null
}
