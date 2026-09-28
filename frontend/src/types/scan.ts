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
  max_gain_pct: number | null
  max_gain_time: string | null
  max_gain_price: number | null
  sp500_close_pct: number | null

  action_time: string | null
  action_fill_price: number | null
  action_best_price: number | null
  action_best_time: string | null
  action_gain_pct: number | null

  price_fill_time: string | null
  price_fill_price: number | null
  price_best_price: number | null
  price_best_time: string | null
  price_gain_pct: number | null

  scanned_at: string
}
