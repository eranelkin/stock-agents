import { useCallback, useEffect, useRef, useState } from 'react'
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
import DeleteIcon from '@mui/icons-material/Delete'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import { createRun, deleteRun, fetchRuns } from '../api/runs'
import type { Run } from '../types/run'

interface RunPageProps {
  selectedModelIds: string[]
}

const STATUS_COLOR: Record<string, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  failed: 'error',
}

const isToday = (dateStr: string) =>
  new Date(dateStr).toDateString() === new Date().toDateString()

export default function RunPage({ selectedModelIds }: RunPageProps) {
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [parsedTickers, setParsedTickers] = useState<Record<string, unknown>[] | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [innerTab, setInnerTab] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const load = useCallback(async () => {
    try {
      setRuns(await fetchRuns())
    } catch {
      // silent — don't block the page
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    return () => stopPolling()
  }, [load])

  // Poll while any run is active
  useEffect(() => {
    const hasActive = runs.some(r => r.status === 'pending' || r.status === 'running')
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const updated = await fetchRuns().catch(() => null)
        if (updated) setRuns(updated)
      }, 2000)
    } else if (!hasActive) {
      stopPolling()
    }
  }, [runs])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null)
    setParsedTickers(null)
    const file = e.target.files?.[0]
    if (!file) { setSelectedFile(null); return }
    setSelectedFile(file)
    try {
      const text = await file.text()
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
      setParsedTickers(parsed as Record<string, unknown>[])
    } catch {
      setFileError('Could not parse file. Make sure it is valid JSON or YAML.')
    }
    // reset input so the same file can be re-selected
    e.target.value = ''
  }

  const handleRun = async () => {
    if (!parsedTickers || !selectedFile) return
    setError(null)
    setStarting(true)
    try {
      const created = await createRun(selectedModelIds, selectedFile.name, parsedTickers)
      setRuns(prev => [created, ...prev])
      setInnerTab(0) // switch to Today tab so user sees the new run
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setStarting(false)
    }
  }

  const handleDelete = async (run: Run) => {
    if (!window.confirm(`Delete run "${run.name ?? 'Unnamed'}"?`)) return
    await deleteRun(run.id)
    setRuns(prev => prev.filter(r => r.id !== run.id))
  }

  const todayRuns = runs.filter(r => isToday(r.created_at))
  const historyRuns = runs.filter(r => !isToday(r.created_at))
  const displayedRuns = innerTab === 0 ? todayRuns : historyRuns

  const runDisabled =
    !selectedFile || !parsedTickers || selectedModelIds.length === 0 || starting

  return (
    <Box sx={{ px: 4, py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
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
                {['Title', 'Status', 'Date & Time'].map((h) => (
                  <TableCell
                    key={h}
                    sx={{
                      color: 'text.secondary',
                      fontSize: '0.8rem',
                      borderColor: 'rgba(255,255,255,0.08)',
                      fontWeight: 600,
                    }}
                  >
                    {h}
                  </TableCell>
                ))}
                <TableCell
                  align="right"
                  sx={{
                    color: 'text.secondary',
                    fontSize: '0.8rem',
                    borderColor: 'rgba(255,255,255,0.08)',
                    fontWeight: 600,
                  }}
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
                      color: 'text.primary',
                      borderColor: 'rgba(255,255,255,0.06)',
                      fontWeight: 500,
                    }}
                  >
                    {run.name ?? 'Unnamed'}
                  </TableCell>
                  <TableCell sx={{ borderColor: 'rgba(255,255,255,0.06)' }}>
                    <Chip
                      label={run.status.toUpperCase()}
                      color={STATUS_COLOR[run.status] ?? 'default'}
                      size="small"
                      sx={{ fontWeight: 700, letterSpacing: 0.5, fontSize: '0.7rem' }}
                    />
                  </TableCell>
                  <TableCell
                    sx={{
                      color: 'text.secondary',
                      borderColor: 'rgba(255,255,255,0.06)',
                      fontSize: '0.85rem',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {new Date(run.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell align="right" sx={{ borderColor: 'rgba(255,255,255,0.06)' }}>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(run)}
                        sx={{ color: '#f44336' }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  )
}
