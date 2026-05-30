export interface PipelineMetadata {
  pipeline_duration_ms: number
  agent_count: number
  timestamp: string
}

export interface PipelineOutput {
  ticker: string
  model_name: string
  agents: Record<string, Record<string, unknown>>
  metadata: PipelineMetadata
}

export interface TickerResult {
  id: string
  run_id: string
  ticker: string
  output: PipelineOutput
  created_at: string
}
