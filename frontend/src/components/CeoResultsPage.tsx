import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TableSortLabel from '@mui/material/TableSortLabel'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CheckIcon from '@mui/icons-material/Check'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import FilterListOffIcon from '@mui/icons-material/FilterListOff'
import type { Run } from '../types/run'

interface CeoResultsPageProps {
  open: boolean
  onClose: () => void
  run: Run
}

type Row = Record<string, unknown> & { _ticker: string; _model: string }

const COLUMN_LABELS: Record<string, string> = {
  volume_dollar: 'VOLUME $',
  ratio_vol_market_cap: 'RATIO VOL - MARKET CAP',
  ai_model_name: 'Model',
}

const COLUMN_ORDER = [
  'symbol',
  'ai_model_name',
  'current price',
  'ceo verdict',
  'conviction score',
  'confidence',
  'success prob',
  'entry range',
  'entry time',
  'sl range',
  'tp range',
  'short_ratio',
  'short_float',
  'institutional_holding',
  'squeeze_risk',
  'approximate_gain_pct',
  'ratio_vol_market_cap',
  'float_turnover_ratio',
  'volume_dollar',
  'conviction_detect',
  'collapse_trigger',
  'catalyst reason',
  'ai_suggestion',
  'required_volume',
  'r-multiple',
  'regime',
  'rvol',
  'poc node',
  'absorption',
  'bid/ask spread',
  'sector sympathy',
  'spx/qqq_corr',
  'date',
]

// Columns whose values are highlighted in red when they exceed a threshold, and the
// header tooltip text explaining that range.
const RED_THRESHOLDS: Record<string, number> = {
  institutional_holding: 83,
  squeeze_risk: 4,
  short_ratio: 8,
  short_float: 12,
}

const HEADER_TOOLTIPS: Record<string, string> = {
  institutional_holding: 'Shown in red when > 83%',
  squeeze_risk: 'Shown in red when > 4',
  short_ratio: 'Shown in red when > 8',
  short_float: 'Shown in red when > 12%',
}

function parseNumeric(value: unknown): number | null {
  if (typeof value === 'number') return value
  if (typeof value !== 'string') return null
  const n = parseFloat(value.replace(/[%,]/g, '').trim())
  return isNaN(n) ? null : n
}

function isOverThreshold(col: string, value: unknown): boolean {
  const threshold = RED_THRESHOLDS[col]
  if (threshold === undefined) return false
  const n = parseNumeric(value)
  return n !== null && n > threshold
}

const LONG_TEXT_COLS = new Set([
  'analysis_strategy',
  'conviction_detect',
  'collapse_trigger',
  'catalyst reason',
  'ai_suggestion',
  'notes',
])

function isLongCol(col: string): boolean {
  return LONG_TEXT_COLS.has(col) || /^reason_\d+$/.test(col)
}

function sortKey(val: unknown): number | string {
  if (val === null || val === undefined) return '￿'
  if (typeof val === 'number') return val
  const s = Array.isArray(val) ? val.join(' ') : String(val)
  if (s === '' || s === '—' || s.toLowerCase() === 'n/a') return '￿'
  const pct = s.endsWith('%') ? parseFloat(s) : NaN
  if (!isNaN(pct)) return pct
  const n = Number(s)
  if (!isNaN(n)) return n
  return s.toLowerCase()
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) return value.join(' | ')
  return String(value)
}

function CellValue({ col, value }: { col: string; value: unknown }) {
  const text = cellText(value)
  const alertSx = isOverThreshold(col, value) ? { color: '#f44336', fontWeight: 700 } : undefined
  if (isLongCol(col)) {
    return (
      <Tooltip
        title={text}
        placement="top"
        arrow
        slotProps={{ tooltip: { sx: { fontSize: '0.8rem', maxWidth: 420 } } }}
      >
        <span style={{
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical' as const,
          overflow: 'hidden',
          whiteSpace: 'normal',
          lineHeight: '1.55',
          cursor: 'default',
          ...alertSx,
        }}>
          {text}
        </span>
      </Tooltip>
    )
  }
  return <span style={alertSx}>{text}</span>
}

function StatItem({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, minWidth: 0 }}>
      <Typography sx={{
        fontSize: '0.6rem', textTransform: 'uppercase',
        letterSpacing: '0.1em', color: 'text.secondary', lineHeight: 1,
      }}>
        {label}
      </Typography>
      <Typography sx={{
        fontSize: '0.95rem', fontWeight: 700, fontFamily: 'monospace',
        color: valueColor ?? 'text.primary', lineHeight: 1.2,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {value}
      </Typography>
    </Box>
  )
}

function FilterInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      value={value}
      placeholder="Filter…"
      onChange={e => onChange(e.target.value)}
      onClick={e => e.stopPropagation()}
      onMouseDown={e => e.stopPropagation()}
      onDragStart={e => e.stopPropagation()}
      draggable={false}
      style={{
        width: '100%',
        boxSizing: 'border-box',
        marginTop: 4,
        padding: '2px 6px',
        fontSize: '0.72rem',
        fontWeight: 400,
        textTransform: 'none',
        letterSpacing: 'normal',
        color: '#e8eaed',
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.14)',
        borderRadius: 4,
        outline: 'none',
      }}
    />
  )
}

function StatSep() {
  return <Box sx={{ width: '1px', height: 30, bgcolor: 'rgba(255,255,255,0.08)', flexShrink: 0 }} />
}

export default function CeoResultsPage({ open, onClose, run }: CeoResultsPageProps) {
  const [rows, setRows] = useState<Row[]>([])
  const [columns, setColumns] = useState<string[]>([])
  const [streamDone, setStreamDone] = useState(false)
  const [dragCol, setDragCol] = useState<number | null>(null)
  const [dragOverCol, setDragOverCol] = useState<number | null>(null)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [groupBy, setGroupBy] = useState<'none' | 'ticker' | 'model'>('none')
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const esRef = useRef<EventSource | null>(null)

  const handleGroupByChange = useCallback((next: 'none' | 'ticker' | 'model') => {
    setGroupBy(next)
    setCollapsedGroups(new Set())
  }, [])

  const handleFilterChange = useCallback((col: string, value: string) => {
    setFilters(prev => ({ ...prev, [col]: value }))
  }, [])

  const handleClearFilters = useCallback(() => setFilters({}), [])

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter(v => v.trim() !== '').length,
    [filters],
  )

  const handleSort = useCallback((col: string) => {
    setSortCol(prev => {
      if (prev === col) {
        setSortDir(d => d === 'asc' ? 'desc' : 'asc')
        return col
      }
      setSortDir('asc')
      return col
    })
  }, [])

  const orderedColumns = useMemo(() => {
    const known = COLUMN_ORDER.filter(c => columns.includes(c))
    const rest = columns.filter(c => !COLUMN_ORDER.includes(c))
    return [...known, ...rest]
  }, [columns])

  const filteredRows = useMemo(() => {
    const active = Object.entries(filters).filter(([, v]) => v.trim() !== '')
    if (active.length === 0) return rows
    return rows.filter(row =>
      active.every(([col, needle]) => {
        const raw = col === '_ticker' ? row._ticker : row[col]
        return cellText(raw).toLowerCase().includes(needle.trim().toLowerCase())
      })
    )
  }, [rows, filters])

  const sortedRows = useMemo(() => {
    if (!sortCol) return filteredRows
    return [...filteredRows].sort((a, b) => {
      const av = sortKey(sortCol === '_ticker' ? a._ticker : a[sortCol])
      const bv = sortKey(sortCol === '_ticker' ? b._ticker : b[sortCol])
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [filteredRows, sortCol, sortDir])

  // Grouping clusters rows by ticker or model, inserting a section header between
  // groups. It re-sorts by the group key as the primary key, but Array.sort is
  // stable, so the existing filter/sort order is preserved *within* each group.
  const groupedRows = useMemo(() => {
    if (groupBy === 'none') return sortedRows
    const keyFn = groupBy === 'ticker' ? (r: Row) => r._ticker : (r: Row) => r._model || '—'
    return [...sortedRows].sort((a, b) => keyFn(a).localeCompare(keyFn(b)))
  }, [sortedRows, groupBy])

  type DisplayItem =
    | { kind: 'header'; label: string; count: number; collapsed: boolean }
    | { kind: 'row'; row: Row }

  const toggleGroupCollapsed = useCallback((label: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }, [])

  const displayItems = useMemo<DisplayItem[]>(() => {
    if (groupBy === 'none') return groupedRows.map(row => ({ kind: 'row', row }))
    const keyFn = groupBy === 'ticker' ? (r: Row) => r._ticker : (r: Row) => r._model || '—'
    const groups = new Map<string, Row[]>()
    for (const row of groupedRows) {
      const key = keyFn(row)
      const bucket = groups.get(key)
      if (bucket) bucket.push(row)
      else groups.set(key, [row])
    }
    const items: DisplayItem[] = []
    for (const [key, groupRows] of groups) {
      const collapsed = collapsedGroups.has(key)
      items.push({ kind: 'header', label: key, count: groupRows.length, collapsed })
      if (!collapsed) {
        for (const row of groupRows) items.push({ kind: 'row', row })
      }
    }
    return items
  }, [groupedRows, groupBy, collapsedGroups])

  const handleDragStart = useCallback((idx: number) => { setDragCol(idx) }, [])
  const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault(); setDragOverCol(idx)
  }, [])
  const handleDrop = useCallback((idx: number) => {
    if (dragCol === null || dragCol === idx) { setDragCol(null); setDragOverCol(null); return }
    setColumns(prev => {
      const next = [...prev]
      const [moved] = next.splice(dragCol, 1)
      next.splice(idx, 0, moved)
      return next
    })
    setDragCol(null); setDragOverCol(null)
  }, [dragCol])
  const handleDragEnd = useCallback(() => { setDragCol(null); setDragOverCol(null) }, [])

  useEffect(() => {
    if (!open) return
    setRows([]); setColumns([]); setStreamDone(false)
    const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
    const es = new EventSource(`${BACKEND}/runs/${run.id}/ceo-stream`)
    esRef.current = es
    es.onmessage = (ev) => {
      try {
        const { ticker, model, data } = JSON.parse(ev.data) as {
          ticker: string
          model: string | null
          data: Record<string, unknown>
        }
        const modelName = model ?? ''
        setColumns(existing => {
          const newCols = Object.keys(data).filter(k => k !== 'symbol' && !existing.includes(k))
          return newCols.length > 0 ? [...existing, ...newCols] : existing
        })
        setRows(prev => {
          if (prev.some(r => r._ticker === ticker && r._model === modelName)) return prev
          // The backend-reported model name is authoritative — it overrides whatever
          // (if anything) the LLM itself self-reported under the same column.
          const row: Row = { _ticker: ticker, _model: modelName, ...data, ai_model_name: modelName || data.ai_model_name }
          return [...prev, row].sort((a, b) =>
            a._ticker.localeCompare(b._ticker) || a._model.localeCompare(b._model)
          )
        })
      } catch { /* ignore */ }
    }
    es.addEventListener('done', () => { setStreamDone(true); es.close(); esRef.current = null })
    es.onerror = () => { setStreamDone(true); es.close(); esRef.current = null }
    return () => { es.close(); esRef.current = null }
  }, [open, run.id])

  const [copied, setCopied] = useState(false)

  const isLive = open && !streamDone

  const stockCount = (() => {
    if (!streamDone && rows.length === 0) return run.ticker_count != null ? String(run.ticker_count) : '—'
    if (run.ticker_count != null && rows.length < run.ticker_count) return `${rows.length} / ${run.ticker_count}`
    return rows.length > 0 ? String(rows.length) : (run.ticker_count != null ? String(run.ticker_count) : '—')
  })()
  const dateStr = new Date(run.created_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
  const modelsStr = run.model_names && run.model_names.length > 0
    ? run.model_names.join('  ·  ')
    : '—'

  const durationStr = (() => {
    if (!run.completed_at) return isLive ? 'Running…' : '—'
    const ms = new Date(run.completed_at).getTime() - new Date(run.created_at).getTime()
    const s = Math.floor(ms / 1000)
    if (s < 60) return `${s}s`
    const m = Math.floor(s / 60)
    const rem = s % 60
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`
  })()

  const handleCopyId = () => {
    navigator.clipboard.writeText(run.id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen
      PaperProps={{ sx: { bgcolor: '#0f1117', display: 'flex', flexDirection: 'column' } }}
    >
      {/* ── Header ── */}
      <Box sx={{
        flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        bgcolor: '#13161f',
      }}>
        {/* Top row: title + status + close */}
        <Box sx={{
          display: 'flex', alignItems: 'flex-start', gap: 2,
          px: 3, pt: 2.5, pb: 1.5,
        }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography sx={{
                fontSize: '1.75rem', fontWeight: 800, letterSpacing: '0.06em',
                textTransform: 'uppercase', color: 'text.primary', lineHeight: 1,
              }}>
                CEO Analysis
              </Typography>
              {run.direction === 'short' ? (
                <Chip
                  label="SHORT"
                  sx={{
                    bgcolor: 'rgba(248,113,113,0.15)',
                    color: '#f87171',
                    border: '1px solid rgba(248,113,113,0.5)',
                    fontWeight: 700,
                    letterSpacing: 1,
                    fontSize: '1.4rem',
                    height: 48,
                    px: 1,
                    animation: 'directionGlowRed 1.8s ease-in-out infinite',
                  }}
                />
              ) : (
                <Chip
                  label="LONG"
                  sx={{
                    bgcolor: 'rgba(52,211,153,0.15)',
                    color: '#34d399',
                    border: '1px solid rgba(52,211,153,0.5)',
                    fontWeight: 700,
                    letterSpacing: 1,
                    fontSize: '1.4rem',
                    height: 48,
                    px: 1,
                    animation: 'directionGlowGreen 1.8s ease-in-out infinite',
                  }}
                />
              )}
            </Box>
            {/* Run ID row */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.75 }}>
              <Typography sx={{
                fontFamily: 'monospace', fontSize: '0.75rem',
                color: 'text.disabled', letterSpacing: '0.02em',
              }}>
                {run.id}
              </Typography>
              <Tooltip title={copied ? 'Copied!' : 'Copy run ID'}>
                <IconButton size="small" onClick={handleCopyId} sx={{
                  p: 0.25,
                  color: copied ? '#4caf50' : 'text.disabled',
                  '&:hover': { color: copied ? '#4caf50' : 'text.secondary' },
                }}>
                  {copied
                    ? <CheckIcon sx={{ fontSize: 13 }} />
                    : <ContentCopyIcon sx={{ fontSize: 13 }} />}
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          <Box sx={{ flex: 1 }} />

          {/* Live / Completed indicator — no chip */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.5 }}>
            <Box sx={{
              width: 7, height: 7, borderRadius: '50%',
              bgcolor: isLive ? '#4caf50' : '#6b7280',
              flexShrink: 0,
              ...(isLive && { animation: 'ceoPulse 1.4s ease-in-out infinite' }),
            }} />
            <Typography sx={{
              fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em',
              color: isLive ? '#4caf50' : 'text.disabled',
              textTransform: 'uppercase',
            }}>
              {isLive ? 'Live' : 'Completed'}
            </Typography>
          </Box>

          <IconButton onClick={onClose} size="small" sx={{
            color: 'text.disabled', mt: 0.25,
            '&:hover': { color: 'text.primary', bgcolor: 'rgba(255,255,255,0.06)' },
          }}>
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.06)', mx: 3 }} />

        {/* Bottom row: stat items */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0, px: 3, py: 1.5 }}>
          <StatItem
            label="Stocks"
            value={stockCount}
            valueColor="#90caf9"
          />
          <Box sx={{ mx: 3 }}><StatSep /></Box>
          <StatItem label="Date & Time" value={dateStr} />
          <Box sx={{ mx: 3 }}><StatSep /></Box>
          <StatItem label="Models" value={modelsStr} valueColor="#90caf9" />
          <Box sx={{ mx: 3 }}><StatSep /></Box>
          <StatItem
            label="Duration"
            value={durationStr}
            valueColor={isLive ? '#fb923c' : undefined}
          />
        </Box>
      </Box>

      {/* ── Content ── */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {rows.length === 0 ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            {isLive ? (
              <>
                <CircularProgress size={36} thickness={3} sx={{ color: '#90caf9' }} />
                <Typography sx={{ color: 'text.disabled', fontSize: '0.9rem' }}>
                  Stock agents are running — CEO analysis appears here when complete.
                </Typography>
                {run.output_dir && (
                  <Box
                    component="a"
                    href={`${import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'}/runs/${run.id}/log`}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{
                      display: 'inline-flex', alignItems: 'center', gap: 0.75,
                      mt: 1, px: 2, py: 0.75,
                      border: '1px solid rgba(144,202,249,0.35)',
                      borderRadius: 1.5,
                      color: '#90caf9',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                      transition: 'background 0.15s, border-color 0.15s',
                      '&:hover': {
                        bgcolor: 'rgba(144,202,249,0.08)',
                        borderColor: '#90caf9',
                      },
                    }}
                  >
                    <OpenInNewIcon sx={{ fontSize: 15 }} />
                    View live pipeline log
                  </Box>
                )}
              </>
            ) : (
              <>
                <Typography sx={{ color: 'text.disabled', fontSize: '0.9rem' }}>
                  No CEO results found for this run.
                </Typography>
                {run.output_dir && (
                  <Box
                    component="a"
                    href={`${import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'}/runs/${run.id}/log`}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{
                      display: 'inline-flex', alignItems: 'center', gap: 0.75,
                      px: 2, py: 0.75,
                      border: '1px solid rgba(255,255,255,0.12)',
                      borderRadius: 1.5,
                      color: 'text.secondary',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                      transition: 'background 0.15s, border-color 0.15s',
                      '&:hover': {
                        bgcolor: 'rgba(255,255,255,0.05)',
                        borderColor: 'rgba(255,255,255,0.25)',
                        color: 'text.primary',
                      },
                    }}
                  >
                    <OpenInNewIcon sx={{ fontSize: 15 }} />
                    View run log
                  </Box>
                )}
              </>
            )}
          </Box>
        ) : (
          <>
            <Box sx={{
              flexShrink: 0,
              display: 'flex', alignItems: 'center', gap: 1.25,
              px: 3, py: 1,
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <Typography sx={{
                fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em',
                textTransform: 'uppercase', color: 'text.secondary',
              }}>
                Group by
              </Typography>
              <ToggleButtonGroup
                value={groupBy}
                exclusive
                size="small"
                onChange={(_, v) => { if (v) handleGroupByChange(v) }}
                sx={{ height: 28 }}
              >
                <ToggleButton value="none" sx={{ px: 1.5, textTransform: 'none', fontSize: '0.75rem', fontWeight: 600 }}>
                  None
                </ToggleButton>
                <ToggleButton value="ticker" sx={{ px: 1.5, textTransform: 'none', fontSize: '0.75rem', fontWeight: 600 }}>
                  Ticker
                </ToggleButton>
                <ToggleButton value="model" sx={{ px: 1.5, textTransform: 'none', fontSize: '0.75rem', fontWeight: 600 }}>
                  Model
                </ToggleButton>
              </ToggleButtonGroup>

              <Box sx={{ flex: 1 }} />

              <Tooltip title={activeFilterCount > 0 ? `Clear ${activeFilterCount} filter${activeFilterCount > 1 ? 's' : ''}` : 'No active filters'}>
                <span>
                  <IconButton
                    size="small"
                    onClick={handleClearFilters}
                    disabled={activeFilterCount === 0}
                    sx={{
                      color: activeFilterCount > 0 ? '#90caf9' : 'text.disabled',
                      '&:hover': { color: '#90caf9', bgcolor: 'rgba(144,202,249,0.08)' },
                    }}
                  >
                    <FilterListOffIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
            <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
            <Table stickyHeader size="small" sx={{ minWidth: 900 }}>
              <TableHead>
                <TableRow>
                  <TableCell
                    sx={{ ...headerCellSx, cursor: 'pointer', position: 'sticky', left: 0, zIndex: 3 }}
                  >
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                      <TableSortLabel
                        active={sortCol === '_ticker'}
                        direction={sortCol === '_ticker' ? sortDir : 'asc'}
                        onClick={() => handleSort('_ticker')}
                        sx={sortLabelSx}
                      >
                        Ticker
                      </TableSortLabel>
                      <FilterInput
                        value={filters['_ticker'] ?? ''}
                        onChange={v => handleFilterChange('_ticker', v)}
                      />
                    </Box>
                  </TableCell>
                  {orderedColumns.map((col, idx) => {
                    const label = COLUMN_LABELS[col] ?? col.replace(/_/g, ' ').replace('approximately gain in %', 'gain %')
                    const tooltip = HEADER_TOOLTIPS[col]
                    return (
                      <TableCell
                        key={col}
                        draggable
                        onDragStart={() => handleDragStart(idx)}
                        onDragOver={e => handleDragOver(e, idx)}
                        onDrop={() => handleDrop(idx)}
                        onDragEnd={handleDragEnd}
                        sx={{
                          ...headerCellSx,
                          cursor: 'grab',
                          opacity: dragCol === idx ? 0.4 : 1,
                          borderLeft: dragOverCol === idx && dragCol !== idx
                            ? '2px solid #90caf9'
                            : '2px solid transparent',
                          userSelect: 'none',
                          '&:active': { cursor: 'grabbing' },
                          ...(isLongCol(col) && { minWidth: 340 }),
                        }}
                      >
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                          <TableSortLabel
                            active={sortCol === col}
                            direction={sortCol === col ? sortDir : 'asc'}
                            onClick={() => handleSort(col)}
                            sx={sortLabelSx}
                          >
                            {tooltip ? (
                              <Tooltip title={tooltip} arrow placement="top">
                                <span>{label}</span>
                              </Tooltip>
                            ) : label}
                          </TableSortLabel>
                          <FilterInput
                            value={filters[col] ?? ''}
                            onChange={v => handleFilterChange(col, v)}
                          />
                        </Box>
                      </TableCell>
                    )
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedRows.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={orderedColumns.length + 1}
                      sx={{ ...dataCellSx, textAlign: 'center', color: 'text.disabled', py: 4 }}
                    >
                      No rows match the current filters.
                    </TableCell>
                  </TableRow>
                )}
                {displayItems.map((item, i) => item.kind === 'header' ? (
                  <TableRow key={`group-${item.label}-${i}`}>
                    <TableCell
                      colSpan={orderedColumns.length + 1}
                      onClick={() => toggleGroupCollapsed(item.label)}
                      sx={{
                        ...dataCellSx,
                        bgcolor: '#161a24',
                        color: '#90caf9',
                        fontWeight: 700,
                        fontSize: '0.75rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        py: 0.75,
                        position: 'sticky',
                        left: 0,
                        cursor: 'pointer',
                        userSelect: 'none',
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box
                          component="span"
                          sx={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 16,
                            height: 16,
                            borderRadius: '3px',
                            border: '1px solid rgba(144,202,249,0.4)',
                            fontFamily: 'monospace',
                            fontSize: '0.75rem',
                            lineHeight: 1,
                            flexShrink: 0,
                          }}
                        >
                          {item.collapsed ? '+' : '−'}
                        </Box>
                        <span>
                          {groupBy === 'ticker' ? 'Ticker' : 'Model'}: {item.label} ({item.count})
                        </span>
                      </Box>
                    </TableCell>
                  </TableRow>
                ) : (
                  <TableRow
                    key={`${item.row._ticker}::${item.row._model}`}
                    sx={{
                      borderLeft: '3px solid transparent',
                      transition: 'background-color 0.15s, border-left-color 0.15s',
                      '&:hover': {
                        bgcolor: 'rgba(255,255,255,0.03)',
                        borderLeft: '3px solid rgba(144,202,249,0.35)',
                      },
                    }}
                  >
                    <TableCell sx={{
                      ...dataCellSx,
                      fontWeight: 700,
                      color: '#90caf9',
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                      bgcolor: '#0f1117',
                      whiteSpace: 'nowrap',
                      position: 'sticky',
                      left: 0,
                      zIndex: 1,
                    }}>
                      {item.row._ticker}
                    </TableCell>
                    {orderedColumns.map(col => (
                      <TableCell
                        key={col}
                        sx={{ ...dataCellSx, ...(isLongCol(col) && { whiteSpace: 'normal' }) }}
                      >
                        <CellValue col={col} value={item.row[col]} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </TableContainer>
          </>
        )}
      </Box>

      <style>{`
        @keyframes ceoPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.35; transform: scale(0.85); }
        }
        @keyframes directionGlowRed {
          0%, 100% { box-shadow: 0 0 6px 0 rgba(248,113,113,0.4); }
          50% { box-shadow: 0 0 18px 4px rgba(248,113,113,0.9); }
        }
        @keyframes directionGlowGreen {
          0%, 100% { box-shadow: 0 0 6px 0 rgba(52,211,153,0.4); }
          50% { box-shadow: 0 0 18px 4px rgba(52,211,153,0.9); }
        }
      `}</style>
    </Dialog>
  )
}

const sortLabelSx = {
  color: 'inherit !important',
  '& .MuiTableSortLabel-icon': { color: 'rgba(255,255,255,0.25) !important' },
  '&.Mui-active': { color: '#90caf9 !important' },
  '&.Mui-active .MuiTableSortLabel-icon': { color: '#90caf9 !important' },
}

const headerCellSx = {
  bgcolor: '#0f1117',
  color: 'text.secondary',
  fontSize: '0.8rem',
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.08em',
  whiteSpace: 'nowrap' as const,
  borderBottom: '1px solid rgba(255,255,255,0.08)',
  py: 1.25,
  px: 2,
}

const dataCellSx = {
  color: 'text.primary',
  fontSize: '0.85rem',
  borderBottom: '1px solid rgba(255,255,255,0.06)',
  whiteSpace: 'nowrap' as const,
  verticalAlign: 'top',
  py: 1.25,
  px: 2,
}
