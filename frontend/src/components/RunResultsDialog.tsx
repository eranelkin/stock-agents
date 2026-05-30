import { useEffect, useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Collapse from '@mui/material/Collapse'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import AccessTimeOutlinedIcon from '@mui/icons-material/AccessTimeOutlined'
import CloseIcon from '@mui/icons-material/Close'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined'
import TimerOutlinedIcon from '@mui/icons-material/TimerOutlined'
import { fetchResults } from '../api/results'
import type { TickerResult } from '../types/result'

interface RunResultsDialogProps {
  open: boolean
  onClose: () => void
  runId: string
  runName?: string | null
}

// ── JSON renderer ────────────────────────────────────────────────────────────

function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const mono: React.CSSProperties = { fontFamily: 'monospace', fontSize: '0.84rem' }

  if (value === null || value === undefined) {
    return <span style={{ ...mono, color: '#616161' }}>null</span>
  }
  if (typeof value === 'boolean') {
    return <span style={{ ...mono, color: '#ffb74d' }}>{String(value)}</span>
  }
  if (typeof value === 'number') {
    return <span style={{ ...mono, color: '#80deea' }}>{value}</span>
  }
  if (typeof value === 'string') {
    if (value.length > 80) {
      return (
        <Typography sx={{ color: '#a5d6a7', fontSize: '0.84rem', lineHeight: 1.65, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {value}
        </Typography>
      )
    }
    return <span style={{ ...mono, color: '#a5d6a7' }}>"{value}"</span>
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span style={{ ...mono, color: 'rgba(255,255,255,0.3)' }}>[]</span>
    }
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, pl: depth > 0 ? 2 : 0 }}>
        {value.map((item, i) => (
          <Box key={i} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <Typography sx={{ color: 'rgba(255,255,255,0.25)', fontFamily: 'monospace', fontSize: '0.75rem', mt: '3px', minWidth: 18, userSelect: 'none' }}>
              {i}.
            </Typography>
            <JsonValue value={item} depth={depth + 1} />
          </Box>
        ))}
      </Box>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) {
      return <span style={{ ...mono, color: 'rgba(255,255,255,0.3)' }}>{'{}'}</span>
    }
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.9, pl: depth > 0 ? 2 : 0 }}>
        {entries.map(([k, v]) => (
          <Box
            key={k}
            sx={{ display: 'grid', gridTemplateColumns: 'minmax(110px, 190px) 1fr', gap: 1.5, alignItems: 'flex-start' }}
          >
            <Typography sx={{ color: '#90caf9', fontFamily: 'monospace', fontSize: '0.82rem', fontWeight: 500, pt: '2px', wordBreak: 'break-all' }}>
              {k}
            </Typography>
            <Box>
              <JsonValue value={v} depth={depth + 1} />
            </Box>
          </Box>
        ))}
      </Box>
    )
  }
  return <span style={{ ...mono, color: '#e8eaed' }}>{String(value)}</span>
}

// ── Sub-components ───────────────────────────────────────────────────────────

function MetaStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ color: 'rgba(255,255,255,0.35)', display: 'flex', alignItems: 'center' }}>{icon}</Box>
      <Box>
        <Typography sx={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: 0.8, lineHeight: 1 }}>
          {label}
        </Typography>
        <Typography sx={{ fontSize: '0.85rem', color: '#e8eaed', fontWeight: 600, lineHeight: 1.3, mt: 0.3 }}>
          {value}
        </Typography>
      </Box>
    </Box>
  )
}

function AgentCard({ title, data }: { title: string; data: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(true)
  const displayTitle = title.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  return (
    <Box sx={{
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 2,
      transition: 'border-color 0.2s, box-shadow 0.2s',
      '&:hover': {
        borderColor: 'rgba(255,255,255,0.16)',
        boxShadow: '0 0 0 1px rgba(25,118,210,0.12)',
      },
    }}>
      <Box
        onClick={() => setExpanded(e => !e)}
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          px: 2.5, py: 1.5, cursor: 'pointer',
          bgcolor: 'rgba(255,255,255,0.03)',
          borderBottom: expanded ? '1px solid rgba(255,255,255,0.06)' : 'none',
          userSelect: 'none',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: '#1976d2', flexShrink: 0 }} />
          <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', color: '#e8eaed' }}>
            {displayTitle}
          </Typography>
        </Box>
        <ExpandMoreIcon sx={{
          color: 'rgba(255,255,255,0.4)', fontSize: 18,
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
        }} />
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ p: 2.5 }}>
          <JsonValue value={data} depth={0} />
        </Box>
      </Collapse>
    </Box>
  )
}

// ── Main dialog ──────────────────────────────────────────────────────────────

export default function RunResultsDialog({ open, onClose, runId, runName }: RunResultsDialogProps) {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchResults(runId)
      .then(data => {
        setResults(data)
        const first = data[0]
        setSelectedTicker(first?.ticker ?? null)
        setSelectedModel(first?.output.model_name ?? null)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!open || !runId) return
    load()
  }, [open, runId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Group results by ticker
  const resultsByTicker = new Map<string, TickerResult[]>()
  for (const r of results) {
    const arr = resultsByTicker.get(r.ticker) ?? []
    arr.push(r)
    resultsByTicker.set(r.ticker, arr)
  }
  const uniqueTickers = [...resultsByTicker.keys()].sort()

  const tickerResults = selectedTicker ? (resultsByTicker.get(selectedTicker) ?? []) : []
  const models = tickerResults.map(r => r.output.model_name)
  const activeResult = tickerResults.find(r => r.output.model_name === selectedModel) ?? tickerResults[0]

  const handleTickerSelect = (ticker: string) => {
    setSelectedTicker(ticker)
    const first = resultsByTicker.get(ticker)?.[0]
    setSelectedModel(first?.output.model_name ?? null)
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xl"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#0a0a0f',
          borderRadius: 2,
          border: '1px solid rgba(255,255,255,0.10)',
          height: '90vh',
          overflow: 'hidden',
          backgroundImage: 'radial-gradient(ellipse at top left, rgba(25,118,210,0.07) 0%, transparent 55%)',
        },
      }}
    >
      {/* Header */}
      <DialogTitle sx={{
        px: 3, py: 1.75,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', alignItems: 'center', gap: 2,
        flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff', flexShrink: 0 }}>
            Run Results
          </Typography>
          {runName && (
            <Typography noWrap sx={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.88rem' }}>
              {runName}
            </Typography>
          )}
          <Chip
            label={runId.slice(0, 8) + '…'}
            size="small"
            sx={{
              fontFamily: 'monospace', fontSize: '0.7rem', flexShrink: 0,
              bgcolor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.45)',
              border: '1px solid rgba(255,255,255,0.10)',
            }}
          />
          {results.length > 0 && (
            <Typography sx={{ color: '#1976d2', fontSize: '0.8rem', fontWeight: 600, flexShrink: 0 }}>
              {results.length} result{results.length !== 1 ? 's' : ''}
            </Typography>
          )}
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: 'rgba(255,255,255,0.4)', '&:hover': { color: '#fff' } }}>
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </DialogTitle>

      {/* Body */}
      <DialogContent sx={{ p: 0, display: 'flex', overflow: 'hidden', flex: 1 }}>
        {loading ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
            <Box sx={{
              '@keyframes pulse': {
                '0%, 100%': { opacity: 0.6, transform: 'scale(1)' },
                '50%': { opacity: 1, transform: 'scale(1.08)' },
              },
              animation: 'pulse 1.8s ease-in-out infinite',
            }}>
              <CircularProgress size={44} thickness={2} sx={{ color: '#1976d2' }} />
            </Box>
            <Typography sx={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.875rem' }}>
              Loading results…
            </Typography>
          </Box>
        ) : error ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, px: 4 }}>
            <Alert severity="error" sx={{ width: '100%', maxWidth: 480 }}>{error}</Alert>
            <Button variant="outlined" size="small" onClick={load} sx={{ textTransform: 'none' }}>
              Retry
            </Button>
          </Box>
        ) : results.length === 0 ? (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.95rem' }}>
              No results found for this run.
            </Typography>
          </Box>
        ) : (
          <>
            {/* Ticker sidebar */}
            <Box sx={{
              width: 220, flexShrink: 0,
              borderRight: '1px solid rgba(255,255,255,0.08)',
              display: 'flex', flexDirection: 'column',
              overflowY: 'auto', bgcolor: 'rgba(0,0,0,0.25)',
            }}>
              <Typography sx={{
                px: 2, py: 1.5,
                fontSize: '0.68rem', fontWeight: 700,
                letterSpacing: 1.3, color: 'rgba(255,255,255,0.3)',
                textTransform: 'uppercase',
              }}>
                Tickers · {uniqueTickers.length}
              </Typography>
              <Box sx={{ px: 1, pb: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {uniqueTickers.map(ticker => {
                  const selected = ticker === selectedTicker
                  const count = resultsByTicker.get(ticker)?.length ?? 0
                  return (
                    <Box
                      key={ticker}
                      onClick={() => handleTickerSelect(ticker)}
                      sx={{
                        px: 1.5, py: 1, borderRadius: 1.5, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        bgcolor: selected ? 'rgba(25,118,210,0.18)' : 'transparent',
                        border: selected ? '1px solid rgba(25,118,210,0.4)' : '1px solid transparent',
                        transition: 'all 0.15s ease',
                        '&:hover': { bgcolor: selected ? 'rgba(25,118,210,0.22)' : 'rgba(255,255,255,0.06)' },
                      }}
                    >
                      <Typography sx={{
                        fontWeight: 700, fontSize: '0.95rem',
                        fontFamily: 'monospace', letterSpacing: 1.5,
                        color: selected ? '#90caf9' : '#fff',
                      }}>
                        {ticker}
                      </Typography>
                      {count > 1 && (
                        <Typography sx={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', fontWeight: 500 }}>
                          ×{count}
                        </Typography>
                      )}
                    </Box>
                  )
                })}
              </Box>
            </Box>

            {/* Main panel */}
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
              {/* Model tabs — only when ticker has multiple model results */}
              {models.length > 1 && (
                <Tabs
                  value={selectedModel ?? models[0]}
                  onChange={(_, v: string) => setSelectedModel(v)}
                  sx={{
                    px: 3, flexShrink: 0,
                    borderBottom: '1px solid rgba(255,255,255,0.08)',
                    minHeight: 44,
                    '& .MuiTab-root': {
                      textTransform: 'none', minHeight: 44, fontSize: '0.85rem',
                      color: 'rgba(255,255,255,0.45)',
                      '&.Mui-selected': { color: '#90caf9', fontWeight: 600 },
                    },
                  }}
                  TabIndicatorProps={{ style: { backgroundColor: '#1976d2', height: 2 } }}
                >
                  {models.map(m => <Tab key={m} value={m} label={m} />)}
                </Tabs>
              )}

              {/* Metadata bar */}
              {activeResult && (
                <Box sx={{
                  display: 'flex', alignItems: 'center', gap: 0,
                  px: 3, py: 1.5, flexShrink: 0,
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                  bgcolor: 'rgba(255,255,255,0.02)',
                }}>
                  <MetaStat
                    icon={<TimerOutlinedIcon sx={{ fontSize: 16 }} />}
                    label="Duration"
                    value={`${(activeResult.output.metadata.pipeline_duration_ms / 1000).toFixed(2)}s`}
                  />
                  <Divider orientation="vertical" flexItem sx={{ mx: 3, borderColor: 'rgba(255,255,255,0.08)' }} />
                  <MetaStat
                    icon={<SmartToyOutlinedIcon sx={{ fontSize: 16 }} />}
                    label="Agents"
                    value={String(activeResult.output.metadata.agent_count)}
                  />
                  <Divider orientation="vertical" flexItem sx={{ mx: 3, borderColor: 'rgba(255,255,255,0.08)' }} />
                  <MetaStat
                    icon={<AccessTimeOutlinedIcon sx={{ fontSize: 16 }} />}
                    label="Completed"
                    value={new Date(activeResult.output.metadata.timestamp).toLocaleString()}
                  />
                  <Box sx={{ flex: 1 }} />
                  <Typography sx={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'rgba(255,255,255,0.2)' }}>
                    {activeResult.output.model_name}
                  </Typography>
                </Box>
              )}

              {/* Agent cards — scrollable */}
              <Box sx={{ flex: 1, overflowY: 'auto', p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {activeResult
                  ? Object.entries(activeResult.output.agents).map(([title, data]) => (
                      <AgentCard key={title} title={title} data={data} />
                    ))
                  : (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
                      <Typography sx={{ color: 'rgba(255,255,255,0.3)' }}>Select a ticker to view results.</Typography>
                    </Box>
                  )
                }
              </Box>
            </Box>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
