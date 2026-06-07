import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
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
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord'

interface CeoResultsPageProps {
  open: boolean
  onClose: () => void
  runId: string
  runName?: string | null
}

type Row = Record<string, unknown> & { _ticker: string }

const LONG_TEXT_COLS = new Set(['conviction_detect', 'collapse_trigger', 'catalyst_reason'])
const MAX_CELL_LEN = 60

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
  if (LONG_TEXT_COLS.has(col) && text.length > MAX_CELL_LEN) {
    return (
      <Tooltip title={text} placement="top" arrow>
        <span style={{ cursor: 'default' }}>{text.slice(0, MAX_CELL_LEN)}…</span>
      </Tooltip>
    )
  }
  return <>{text}</>
}

export default function CeoResultsPage({ open, onClose, runId, runName }: CeoResultsPageProps) {
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

  const handleDragStart = useCallback((idx: number) => {
    setDragCol(idx)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault()
    setDragOverCol(idx)
  }, [])

  const handleDrop = useCallback((idx: number) => {
    if (dragCol === null || dragCol === idx) {
      setDragCol(null)
      setDragOverCol(null)
      return
    }
    setColumns(prev => {
      const next = [...prev]
      const [moved] = next.splice(dragCol, 1)
      next.splice(idx, 0, moved)
      return next
    })
    setDragCol(null)
    setDragOverCol(null)
  }, [dragCol])

  const handleDragEnd = useCallback(() => {
    setDragCol(null)
    setDragOverCol(null)
  }, [])

  useEffect(() => {
    if (!open) return
    setRows([])
    setColumns([])
    setStreamDone(false)

    const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
    const es = new EventSource(`${BACKEND}/runs/${runId}/ceo-stream`)
    esRef.current = es

    es.onmessage = (ev) => {
      try {
        const { ticker, data } = JSON.parse(ev.data) as { ticker: string; data: Record<string, unknown> }
        setRows(prev => {
          if (prev.some(r => r._ticker === ticker)) return prev
          if (prev.length === 0) setColumns(Object.keys(data))
          return [...prev, { _ticker: ticker, ...data }].sort((a, b) =>
            a._ticker.localeCompare(b._ticker)
          )
        })
      } catch { /* ignore malformed frame */ }
    }

    es.addEventListener('done', () => {
      setStreamDone(true)
      es.close()
      esRef.current = null
    })

    es.onerror = () => {
      setStreamDone(true)
      es.close()
      esRef.current = null
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [open, runId])

  const isLive = open && !streamDone

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen
      PaperProps={{ sx: { bgcolor: '#0f1117', display: 'flex', flexDirection: 'column' } }}
    >
      {/* ── Header ── */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1.5, px: 3, py: 1.5,
        borderBottom: '1px solid rgba(255,255,255,0.08)', flexShrink: 0,
      }}>
        <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 0.5 }}>
          CEO Results
        </Typography>

        {runName && (
          <Chip label={runName} size="small" variant="outlined"
            sx={{ borderColor: 'rgba(255,255,255,0.2)', color: 'rgba(255,255,255,0.7)', fontSize: '0.75rem' }} />
        )}

        <Chip
          label={`${runId.slice(0, 8)}…`}
          size="small"
          sx={{ fontFamily: 'monospace', fontSize: '0.72rem', bgcolor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)' }}
        />

        <Box sx={{ flex: 1 }} />

        {/* Live / Done badge */}
        {isLive ? (
          <Chip
            icon={<FiberManualRecordIcon sx={{ fontSize: '10px !important', color: '#4caf50 !important', animation: 'pulse 1.4s ease-in-out infinite' }} />}
            label="Live"
            size="small"
            sx={{ bgcolor: 'rgba(76,175,80,0.12)', color: '#4caf50', border: '1px solid rgba(76,175,80,0.3)', fontSize: '0.72rem' }}
          />
        ) : (
          <Chip label="Done" size="small"
            sx={{ bgcolor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.4)', fontSize: '0.72rem' }} />
        )}

        {rows.length > 0 && (
          <Chip label={`${rows.length} ticker${rows.length !== 1 ? 's' : ''}`} size="small"
            sx={{ bgcolor: 'rgba(144,202,249,0.1)', color: '#90caf9', fontSize: '0.72rem' }} />
        )}

        <IconButton onClick={onClose} size="small" sx={{ color: 'rgba(255,255,255,0.5)', ml: 0.5 }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* ── Content ── */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {rows.length === 0 ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            {isLive ? (
              <>
                <CircularProgress size={36} thickness={3} sx={{ color: '#90caf9' }} />
                <Typography sx={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem' }}>
                  Waiting for CEO analysis…
                </Typography>
              </>
            ) : (
              <Typography sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.9rem' }}>
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
                  <TableRow key={row._ticker} hover sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' } }}>
                    <TableCell sx={{ ...dataCellSx, fontWeight: 700, color: '#90caf9', fontFamily: 'monospace' }}>
                      {row._ticker}
                    </TableCell>
                    {columns.map(col => (
                      <TableCell key={col} sx={dataCellSx}>
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
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </Dialog>
  )
}

const sortLabelSx = {
  color: 'inherit !important',
  '& .MuiTableSortLabel-icon': { color: 'rgba(255,255,255,0.35) !important' },
  '&.Mui-active': { color: '#90caf9 !important' },
  '&.Mui-active .MuiTableSortLabel-icon': { color: '#90caf9 !important' },
}

const headerCellSx = {
  bgcolor: '#161b27',
  color: 'rgba(255,255,255,0.55)',
  fontSize: '0.72rem',
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.06em',
  whiteSpace: 'nowrap' as const,
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  py: 1.2,
  px: 1.5,
}

const dataCellSx = {
  color: 'rgba(255,255,255,0.82)',
  fontSize: '0.8rem',
  borderBottom: '1px solid rgba(255,255,255,0.05)',
  whiteSpace: 'nowrap' as const,
  py: 1,
  px: 1.5,
}
