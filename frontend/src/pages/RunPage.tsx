import { useEffect, useRef, useState } from 'react'
import * as jsyaml from 'js-yaml'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Divider from '@mui/material/Divider'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import TableSortLabel from '@mui/material/TableSortLabel'
import DeleteIcon from '@mui/icons-material/Delete'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CheckIcon from '@mui/icons-material/Check'
import ArticleIcon from '@mui/icons-material/Article'
import { createRun, deleteRun, stopRun } from '../api/runs'
import CeoResultsPage from '../components/CeoResultsPage'
import type { Run } from '../types/run'

interface RunPageProps {
  selectedModelIds: string[]
  onRunActiveChange?: (active: boolean) => void
}

const STATUS_COLOR: Record<string, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
}

const isToday = (dateStr: string) =>
  new Date(dateStr).toDateString() === new Date().toDateString()

const formatDuration = (ms: number): string => {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`
}

export default function RunPage({ selectedModelIds, onRunActiveChange }: RunPageProps) {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [rawFileText, setRawFileText] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [innerTab, setInnerTab] = useState(0)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [resultsRun, setResultsRun] = useState<Run | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [now, setNow] = useState(() => Date.now())
  const fileInputRef = useRef<HTMLInputElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Open SSE connection once on mount; first message delivers current run list
  useEffect(() => {
    const BACKEND = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'
    const es = new EventSource(`${BACKEND}/runs/stream`)
    esRef.current = es
    es.onmessage = (ev) => {
      try {
        setRuns(JSON.parse(ev.data) as Run[])
        setLoading(false)
      } catch { /* ignore malformed frame */ }
    }
    return () => {
      es.close()
      esRef.current = null
      if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
    }
  }, [])

  // Live duration tick + parent notification when active-run state changes
  useEffect(() => {
    const hasActive = runs.some(r => r.status === 'pending' || r.status === 'running')
    onRunActiveChange?.(hasActive)
    if (hasActive) {
      if (!tickRef.current) tickRef.current = setInterval(() => setNow(Date.now()), 1000)
    } else {
      if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
    }
  }, [runs, onRunActiveChange])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null)
    setRawFileText(null)
    const file = e.target.files?.[0]
    if (!file) { setSelectedFile(null); return }
    setSelectedFile(file)
    try {
      const text = await file.text()
      setRawFileText(text)
      const lower = file.name.toLowerCase()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let parsed: any
      if (lower.endsWith('.yaml') || lower.endsWith('.yml')) {
        parsed = jsyaml.load(text)
      } else {
        parsed = JSON.parse(text)
      }
      if (!Array.isArray(parsed)) {
        setFileError('File must contain a JSON/YAML array of ticker objects, e.g. [{"name":"AAPL"}]')
        return
      }
      if (parsed.length === 0) {
        setFileError('Ticker list is empty.')
        return
      }
    } catch {
      setFileError('Could not parse file. Make sure it is valid JSON or YAML.')
    }
    // reset input so the same file can be re-selected
    e.target.value = ''
  }

  const formatCurrentDate = () => {
    const now = new Date()
    const date = now.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' })
    const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/New_York' })
    const tz = now.toLocaleTimeString('en-US', { timeZoneName: 'short', timeZone: 'America/New_York' }).split(' ').pop() ?? 'ET'
    return `${date}, ${time} ${tz}`
  }

  const handleRun = async () => {
    if (!rawFileText || !selectedFile) return
    setError(null)
    setStarting(true)
    try {
      const processedText = rawFileText.replace(/CURRENT_DATE/g, formatCurrentDate())
      const lower = selectedFile.name.toLowerCase()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let tickers: Record<string, unknown>[]
      if (lower.endsWith('.yaml') || lower.endsWith('.yml')) {
        tickers = jsyaml.load(processedText) as Record<string, unknown>[]
      } else {
        tickers = JSON.parse(processedText)
      }
      const created = await createRun(selectedModelIds, selectedFile.name, tickers)
      setRuns(prev => [created, ...prev])
      setInnerTab(0) // switch to Today tab so user sees the new run
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async (run: Run) => {
    if (!window.confirm(`Stop run "${run.name ?? 'Unnamed'}"? This will cancel all active pipelines.`)) return
    try {
      await stopRun(run.id)
      // SSE broadcaster will push the updated status automatically
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop run')
    }
  }

  const handleDelete = async (run: Run) => {
    if (!window.confirm(`Delete run "${run.name ?? 'Unnamed'}"?`)) return
    await deleteRun(run.id)
    setRuns(prev => prev.filter(r => r.id !== run.id))
  }

  const todayRuns = runs.filter(r => isToday(r.created_at))
  const historyRuns = runs.filter(r => !isToday(r.created_at))
  const sorted = (innerTab === 0 ? todayRuns : historyRuns).slice().sort((a, b) => {
    const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    return sortOrder === 'asc' ? diff : -diff
  })
  const displayedRuns = sorted

  const runInProgress = runs.some(r => r.status === 'pending' || r.status === 'running')
  const runDisabled =
    !selectedFile || !rawFileText || selectedModelIds.length === 0 || starting || runInProgress

  return (
    <Box sx={{ px: 4, py: 3, display: 'flex', flexDirection: 'column', gap: 2, flex: 1, overflow: 'hidden' }}>
      {/* Page header */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="text.primary">
            Runs
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Execute AI pipelines on your stock tickers.
          </Typography>
        </Box>

        {/* File picker + Run button */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 0.5 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.yaml,.yml"
            hidden
            onChange={handleFileChange}
          />
          <Box
            onClick={() => fileInputRef.current?.click()}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.75,
              py: 0.75,
              borderRadius: 1.5,
              border: '1px solid rgba(255,255,255,0.12)',
              bgcolor: 'rgba(255,255,255,0.04)',
              cursor: 'pointer',
              minWidth: 180,
              maxWidth: 260,
              '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
            }}
          >
            <AttachFileIcon sx={{ fontSize: 16, color: 'text.secondary', flexShrink: 0 }} />
            <Typography
              variant="body2"
              color={selectedFile ? 'text.primary' : 'text.secondary'}
              noWrap
              sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}
            >
              {selectedFile ? selectedFile.name : 'Choose file…'}
            </Typography>
          </Box>

          <Button
            variant="contained"
            startIcon={starting ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
            onClick={handleRun}
            disabled={runDisabled}
            sx={{
              borderRadius: 1.5,
              px: 3,
              textTransform: 'none',
              fontWeight: 600,
              whiteSpace: 'nowrap',
            }}
          >
            {starting ? 'Starting…' : 'Run'}
          </Button>
        </Box>
      </Box>

      {/* Inline error messages */}
      {fileError && <Alert severity="error" onClose={() => setFileError(null)}>{fileError}</Alert>}
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {selectedModelIds.length === 0 && selectedFile && (
        <Alert severity="warning">Select one or more models from the header dropdown.</Alert>
      )}

      <Divider />

      {/* Inner tabs */}
      <Tabs
        value={innerTab}
        onChange={(_, v: number) => setInnerTab(v)}
        TabIndicatorProps={{ style: { backgroundColor: '#1976d2', height: 2 } }}
        sx={{ minHeight: 40 }}
      >
        {(['Today', 'History'] as const).map((label) => (
          <Tab
            key={label}
            label={label}
            sx={{
              minHeight: 40,
              textTransform: 'none',
              fontWeight: 500,
              fontSize: '0.875rem',
              color: 'text.secondary',
              px: 2,
              '&.Mui-selected': { color: '#1976d2' },
            }}
          />
        ))}
      </Tabs>

      {/* Table */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 6 }}>
          <CircularProgress size={28} />
        </Box>
      ) : displayedRuns.length === 0 ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 6 }}>
          <Typography variant="h6" color="text.secondary">
            {innerTab === 0 ? 'No runs today' : 'No historical runs'}
          </Typography>
        </Box>
      ) : (
        <TableContainer>
          <Table size="small" sx={{ width: '100%' }}>
            <TableHead>
              <TableRow>
                <TableCell
                  sx={{ color: 'text.secondary', fontSize: '0.8rem', borderColor: 'rgba(255,255,255,0.08)', fontWeight: 600 }}
                >
                  <TableSortLabel
                    active
                    direction={sortOrder}
                    onClick={() => setSortOrder(o => o === 'asc' ? 'desc' : 'asc')}
                    sx={{
                      color: 'text.secondary !important',
                      '& .MuiTableSortLabel-icon': { color: 'text.secondary !important' },
                    }}
                  >
                    Date & Time
                  </TableSortLabel>
                </TableCell>
                {['Run ID', 'Models', 'Duration', 'Status'].map((h) => (
                  <TableCell
                    key={h}
                    sx={{ color: 'text.secondary', fontSize: '0.8rem', borderColor: 'rgba(255,255,255,0.08)', fontWeight: 600 }}
                  >
                    {h}
                  </TableCell>
                ))}
                <TableCell
                  align="right"
                  sx={{ color: 'text.secondary', fontSize: '0.8rem', borderColor: 'rgba(255,255,255,0.08)', fontWeight: 600 }}
                >
                  Actions
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {displayedRuns.map((run) => (
                <TableRow
                  key={run.id}
                  sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' } }}
                >
                  <TableCell
                    sx={{
                      color: '#ffffff',
                      borderColor: 'rgba(255,255,255,0.06)',
                      fontSize: '0.85rem',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {new Date(run.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell
                    sx={{
                      borderColor: 'rgba(255,255,255,0.06)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Typography
                        onClick={() => setResultsRun(run)}
                        sx={{
                          fontFamily: 'monospace', fontSize: '0.8rem',
                          color: 'text.secondary', cursor: 'pointer',
                          px: 0.75, py: 0.25, borderRadius: 1,
                          transition: 'color 0.15s, background-color 0.15s',
                          '&:hover': { color: '#90caf9', bgcolor: 'rgba(144,202,249,0.10)' },
                        }}
                      >
                        {run.id}
                      </Typography>
                      <Tooltip title={copiedId === run.id ? 'Copied!' : 'Copy ID'}>
                        <IconButton
                          size="small"
                          onClick={() => {
                            navigator.clipboard.writeText(run.id)
                            setCopiedId(run.id)
                            setTimeout(() => setCopiedId(null), 2000)
                          }}
                          sx={{ color: copiedId === run.id ? '#4caf50' : 'text.disabled', '&:hover': { color: copiedId === run.id ? '#4caf50' : 'text.secondary' } }}
                        >
                          {copiedId === run.id
                            ? <CheckIcon sx={{ fontSize: 14 }} />
                            : <ContentCopyIcon sx={{ fontSize: 14 }} />}
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                  <TableCell sx={{ borderColor: 'rgba(255,255,255,0.06)' }}>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {run.model_names && run.model_names.length > 0
                        ? run.model_names.map((name) => (
                            <Chip
                              key={name}
                              label={name}
                              size="small"
                              sx={{ bgcolor: 'rgba(25,118,210,0.15)', color: '#90caf9', fontSize: '0.7rem', height: 20 }}
                            />
                          ))
                        : <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.disabled' }}>—</Typography>
                      }
                    </Box>
                  </TableCell>
                  <TableCell sx={{ borderColor: 'rgba(255,255,255,0.06)', whiteSpace: 'nowrap' }}>
                    {(() => {
                      const start = new Date(run.created_at).getTime()
                      const end = run.completed_at ? new Date(run.completed_at).getTime() : null
                      const active = run.status === 'pending' || run.status === 'running'
                      if (active) {
                        return (
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#fb923c' }}>
                            {formatDuration(now - start)}
                          </Typography>
                        )
                      }
                      if (end) {
                        return (
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'text.secondary' }}>
                            {formatDuration(end - start)}
                          </Typography>
                        )
                      }
                      return <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.disabled' }}>—</Typography>
                    })()}
                  </TableCell>
                  <TableCell sx={{ borderColor: 'rgba(255,255,255,0.06)' }}>
                    <Chip
                      label={run.status.toUpperCase()}
                      color={STATUS_COLOR[run.status] ?? 'default'}
                      size="small"
                      sx={{ fontWeight: 700, letterSpacing: 0.5, fontSize: '0.7rem' }}
                    />
                  </TableCell>
                  <TableCell align="right" sx={{ borderColor: 'rgba(255,255,255,0.06)', whiteSpace: 'nowrap' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.75 }}>
                    {(run.status === 'pending' || run.status === 'running') && (
                      <Tooltip title="Stop run">
                        <Box
                          component="button"
                          onClick={() => handleStop(run)}
                          sx={{
                            width: 34,
                            height: 34,
                            borderRadius: '50%',
                            background: 'radial-gradient(circle at 38% 32%, #ff5c5c 0%, #e00000 55%, #9a0000 100%)',
                            border: '2px solid #1a1a1a',
                            color: '#fff',
                            fontWeight: 800,
                            fontSize: '0.6rem',
                            letterSpacing: '0.02em',
                            textTransform: 'uppercase',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            verticalAlign: 'middle',
                            boxShadow: '0 2px 6px rgba(0,0,0,0.6), inset 0 1px 2px rgba(255,255,255,0.25)',
                            transition: 'transform 0.12s, box-shadow 0.12s',
                            p: 0,
                            lineHeight: 1,
                            '&:hover': {
                              transform: 'scale(1.12)',
                              boxShadow: '0 4px 14px rgba(180,0,0,0.55), inset 0 1px 2px rgba(255,255,255,0.25)',
                            },
                            '&:active': { transform: 'scale(0.94)' },
                          }}
                        >
                          Stop
                        </Box>
                      </Tooltip>
                    )}
                    <Tooltip title="View live log">
                      <span>
                        <IconButton
                          size="small"
                          disabled={!run.output_dir}
                          onClick={() => window.open(
                            `${import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:4101'}/runs/${run.id}/log`,
                            '_blank'
                          )}
                          sx={{ color: 'text.secondary', '&:hover': { color: '#90caf9' }, '&.Mui-disabled': { color: 'text.disabled' } }}
                        >
                          <ArticleIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(run)}
                        sx={{ color: '#f44336' }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      </Box>
      {resultsRun && (
        <CeoResultsPage
          open={Boolean(resultsRun)}
          onClose={() => setResultsRun(null)}
          runId={resultsRun.id}
          runName={resultsRun.name}
        />
      )}
    </Box>
  )
}
