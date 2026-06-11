import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
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
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseIcon from '@mui/icons-material/Close'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CheckIcon from '@mui/icons-material/Check'
import type { Run } from '../types/run'

interface CeoResultsPageProps {
  open: boolean
  onClose: () => void
  run: Run
}

type Row = Record<string, unknown> & { _ticker: string }

const LONG_TEXT_COLS = new Set([
  'analysis_strategy',
  'conviction_detect',
  'collapse_conviction',
  'collapse_trigger',
  'catalyst_reason',
  'volume',
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
        }}>
          {text}
        </span>
      </Tooltip>
    )
  }
  return <>{text}</>
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
  const esRef = useRef<EventSource | null>(null)

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

  const sortedRows = useMemo(() => {
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      const av = sortKey(sortCol === '_ticker' ? a._ticker : a[sortCol])
      const bv = sortKey(sortCol === '_ticker' ? b._ticker : b[sortCol])
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, sortCol, sortDir])

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
        const { ticker, data } = JSON.parse(ev.data) as { ticker: string; data: Record<string, unknown> }
        setRows(prev => {
          if (prev.some(r => r._ticker === ticker)) return prev
          if (prev.length === 0) setColumns(Object.keys(data).filter(k => k !== 'symbol'))
          return [...prev, { _ticker: ticker, ...data }].sort((a, b) => a._ticker.localeCompare(b._ticker))
        })
      } catch { /* ignore */ }
    }
    es.addEventListener('done', () => { setStreamDone(true); es.close(); esRef.current = null })
    es.onerror = () => { setStreamDone(true); es.close(); esRef.current = null }
    return () => { es.close(); esRef.current = null }
  }, [open, run.id])

  const [copied, setCopied] = useState(false)

  const isLive = open && !streamDone

  const stockCount = run.ticker_count ?? (rows.length > 0 ? rows.length : null)
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
            <Typography sx={{
              fontSize: '1.75rem', fontWeight: 800, letterSpacing: '0.06em',
              textTransform: 'uppercase', color: 'text.primary', lineHeight: 1,
            }}>
              CEO Analysis
            </Typography>
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
            value={stockCount != null ? String(stockCount) : '—'}
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
                  Waiting for CEO analysis…
                </Typography>
              </>
            ) : (
              <Typography sx={{ color: 'text.disabled', fontSize: '0.9rem' }}>
                No CEO results found for this run.
              </Typography>
            )}
          </Box>
        ) : (
          <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
            <Table stickyHeader size="small" sx={{ minWidth: 900 }}>
              <TableHead>
                <TableRow>
                  <TableCell
                    sx={{ ...headerCellSx, cursor: 'pointer' }}
                    onClick={() => handleSort('_ticker')}
                  >
                    <TableSortLabel
                      active={sortCol === '_ticker'}
                      direction={sortCol === '_ticker' ? sortDir : 'asc'}
                      onClick={() => handleSort('_ticker')}
                      sx={sortLabelSx}
                    >
                      Ticker
                    </TableSortLabel>
                  </TableCell>
                  {columns.map((col, idx) => (
                    <TableCell
                      key={col}
                      draggable
                      onDragStart={() => handleDragStart(idx)}
                      onDragOver={e => handleDragOver(e, idx)}
                      onDrop={() => handleDrop(idx)}
                      onDragEnd={handleDragEnd}
                      onClick={() => handleSort(col)}
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
                      <TableSortLabel
                        active={sortCol === col}
                        direction={sortCol === col ? sortDir : 'asc'}
                        onClick={() => handleSort(col)}
                        sx={sortLabelSx}
                      >
                        {col.replace(/_/g, ' ').replace('approximately gain in %', 'gain %')}
                      </TableSortLabel>
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedRows.map(row => (
                  <TableRow
                    key={row._ticker}
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
                      background: 'linear-gradient(90deg, rgba(144,202,249,0.07) 0%, transparent 80%)',
                      whiteSpace: 'nowrap',
                    }}>
                      {row._ticker}
                    </TableCell>
                    {columns.map(col => (
                      <TableCell
                        key={col}
                        sx={{ ...dataCellSx, ...(isLongCol(col) && { whiteSpace: 'normal' }) }}
                      >
                        <CellValue col={col} value={row[col]} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <style>{`
        @keyframes ceoPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.35; transform: scale(0.85); }
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
