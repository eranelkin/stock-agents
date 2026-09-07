export interface ScanResult {
  id: string
  run_id: string
  ticker: string

  status: 'completed' | 'no_data' | 'error'
  error_message: string | null

  recommendation: Record<string, unknown>
  entry_low: number | null
  entry_high: number | null
  entry_time_start: string | null
  entry_time_end: string | null
  sl_low: number | null
  sl_high: number | null
  tp_low: number | null
  tp_high: number | null
  entry_window_low: number | null
  entry_window_high: number | null

  fill_status: 'filled' | 'no_fill'
  fill_time: string | null
  fill_price: number | null
  exit_reason: 'take_profit' | 'stop_loss' | 'open_eod' | null
  exit_time: string | null
  exit_price: number | null
  pnl_pct: number | null
  r_multiple: number | null

  scanned_at: string
}
