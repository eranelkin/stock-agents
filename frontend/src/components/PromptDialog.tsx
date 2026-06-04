import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import TextField from '@mui/material/TextField'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import Switch from '@mui/material/Switch'
import FormControlLabel from '@mui/material/FormControlLabel'
import Tooltip from '@mui/material/Tooltip'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import CloseIcon from '@mui/icons-material/Close'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import { createPrompt, updatePrompt } from '../api/prompts'
import type { Prompt } from '../types/prompt'

interface PromptDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
  editPrompt?: Prompt | null
  defaultCategory: string
}

const EMPTY = { title: '', content: '', search_mode: '', search_enabled: false, search_query_template: '' }

const inputSx = {
  '& .MuiOutlinedInput-root': {
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: '6px',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.14)' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.28)' },
    '&.Mui-focused fieldset': { borderColor: '#1976d2', borderWidth: '1px' },
    '&.Mui-focused': { boxShadow: '0 0 0 3px rgba(25,118,210,0.18)' },
  },
  '& .MuiInputBase-input': {
    color: '#e8eaed',
    fontSize: '0.9rem',
  },
  '& textarea::placeholder': { color: '#555', opacity: 1 },
  '& input::placeholder': { color: '#555', opacity: 1 },
}

function InfoTooltip({ content }: { content: React.ReactNode }) {
  return (
    <Tooltip
      title={content}
      placement="right"
      arrow
      slotProps={{
        tooltip: {
          sx: {
            bgcolor: '#1a1e2e',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '10px',
            p: 2,
            maxWidth: 340,
            boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
          },
        },
        arrow: { sx: { color: '#1a1e2e' } },
      }}
    >
      <InfoOutlinedIcon
        sx={{
          fontSize: 15,
          color: 'rgba(255,255,255,0.3)',
          cursor: 'help',
          flexShrink: 0,
          transition: 'color 0.15s',
          '&:hover': { color: '#90caf9' },
        }}
      />
    </Tooltip>
  )
}

function Field({ label, tooltip, children }: { label: string; tooltip?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Typography sx={{ color: '#cdd1d9', fontWeight: 500, fontSize: '0.875rem' }}>
          {label}
        </Typography>
        {tooltip && <InfoTooltip content={tooltip} />}
      </Box>
      {children}
    </Box>
  )
}

export default function PromptDialog({
  open,
  onClose,
  onSaved,
  editPrompt,
  defaultCategory,
}: PromptDialogProps) {
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEdit = Boolean(editPrompt)

  useEffect(() => {
    if (editPrompt) {
      setForm({
        title: editPrompt.title,
        content: editPrompt.content,
        search_mode: editPrompt.search_mode ?? '',
        search_enabled: editPrompt.search_enabled ?? false,
        search_query_template: editPrompt.search_query_template ?? '',
      })
    } else {
      setForm(EMPTY)
    }
    setError(null)
  }, [editPrompt, open])

  const set =
    (field: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }))

  const searchModeValue = form.search_mode || ''
  const resolvedSearchMode = searchModeValue === '' ? null : searchModeValue

  const searchModeTooltip = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography sx={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.82rem' }}>Search Mode</Typography>
      <Typography sx={{ color: '#94a3b8', fontSize: '0.78rem', lineHeight: 1.6 }}>
        Controls how this prompt fetches real-time web data before the LLM processes it.
      </Typography>
      {[
        { label: 'Use global setting', desc: 'Inherits SEARCH_MODE from your .env file. Safe default — all prompts behave the same.' },
        { label: 'Prefetch', desc: 'Your system runs a Tavily search before the LLM call. Results are injected as context. Lower token usage, single clean LLM call.' },
        { label: 'Tool call', desc: 'The LLM decides when and what to search during its response, up to SEARCH_MAX_TOOL_ROUNDS. More flexible but uses significantly more tokens.' },
      ].map(({ label, desc }) => (
        <Box key={label} sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          <Typography sx={{ color: '#93c5fd', fontWeight: 600, fontSize: '0.78rem' }}>{label}</Typography>
          <Typography sx={{ color: '#94a3b8', fontSize: '0.76rem', lineHeight: 1.5 }}>{desc}</Typography>
        </Box>
      ))}
    </Box>
  )

  const enableSearchTooltip = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography sx={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.82rem' }}>Enable Search</Typography>
      <Typography sx={{ color: '#94a3b8', fontSize: '0.78rem', lineHeight: 1.6 }}>
        Gates whether a Tavily web search runs for this prompt in Prefetch mode.
      </Typography>
      {[
        { label: 'ON', desc: 'A search runs before the LLM call. Results are appended to the user message as a search_context block, giving the model fresh real-time data.' },
        { label: 'OFF', desc: 'No search is performed. The LLM relies only on the input data you provide (stock fields from your JSON/YAML file).' },
      ].map(({ label, desc }) => (
        <Box key={label} sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          <Typography sx={{ color: '#93c5fd', fontWeight: 600, fontSize: '0.78rem' }}>{label}</Typography>
          <Typography sx={{ color: '#94a3b8', fontSize: '0.76rem', lineHeight: 1.5 }}>{desc}</Typography>
        </Box>
      ))}
    </Box>
  )

  const queryTemplateTooltip = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography sx={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.82rem' }}>Search Query Template</Typography>
      <Typography sx={{ color: '#94a3b8', fontSize: '0.78rem', lineHeight: 1.6 }}>
        The exact query sent to Tavily. Use <Box component="span" sx={{ color: '#fbbf24', fontFamily: 'monospace' }}>{'{ticker}'}</Box> as a placeholder — it's replaced with the stock symbol at runtime.
      </Typography>
      <Box sx={{ bgcolor: 'rgba(255,255,255,0.06)', borderRadius: '6px', p: 1 }}>
        <Typography sx={{ color: '#86efac', fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {'{ticker}'} pre-market price short interest today
        </Typography>
        <Typography sx={{ color: '#64748b', fontSize: '0.73rem', mt: 0.5 }}>→ "POET pre-market price short interest today"</Typography>
      </Box>
      <Typography sx={{ color: '#94a3b8', fontSize: '0.76rem', lineHeight: 1.5 }}>
        If left empty, falls back to a default query: <Box component="span" sx={{ color: '#fbbf24', fontFamily: 'monospace', fontSize: '0.73rem' }}>{'{ticker}'} stock latest news research 2026</Box>
      </Typography>
      <Typography sx={{ color: '#64748b', fontSize: '0.75rem', fontStyle: 'italic' }}>
        Tip: Include "today" or "pre-market" to prioritize fresh data from Tavily.
      </Typography>
    </Box>
  )

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.content.trim()) {
      setError('Title and Prompt are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const searchPayload = {
        search_mode: resolvedSearchMode,
        search_enabled: resolvedSearchMode === 'prefetch' ? form.search_enabled : false,
        search_query_template: (resolvedSearchMode === 'prefetch' && form.search_enabled)
          ? (form.search_query_template.trim() || null)
          : null,
      }
      if (isEdit && editPrompt) {
        await updatePrompt(editPrompt.id, { title: form.title, content: form.content, category: defaultCategory, ...searchPayload })
      } else {
        await createPrompt({ title: form.title, content: form.content, category: defaultCategory, ...searchPayload })
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#000',
          borderRadius: 2,
          border: '1px solid rgba(255,255,255,0.12)',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pt: 2.5,
          pb: 1.5,
          px: 3,
        }}
      >
        <Typography sx={{ color: '#fff', fontWeight: 600, fontSize: '1.05rem' }}>
          {isEdit ? 'Edit Prompt' : 'Add Prompt'}
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{ color: 'rgba(255,255,255,0.45)', '&:hover': { color: '#fff', bgcolor: 'transparent' } }}
        >
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, px: 3, pb: 2, pt: 0.5 }}>
        <Field label="Title">
          <TextField
            placeholder="e.g. Financial Data Collector"
            value={form.title}
            onChange={set('title')}
            fullWidth
            size="small"
            sx={inputSx}
          />
        </Field>

        <Field label="Prompt">
          <TextField
            placeholder="Enter the prompt text…"
            value={form.content}
            onChange={set('content')}
            fullWidth
            multiline
            rows={6}
            sx={inputSx}
          />
        </Field>

        <Field label="Search Mode" tooltip={searchModeTooltip}>
          <Select
            value={searchModeValue}
            onChange={(e) => setForm((f) => ({ ...f, search_mode: e.target.value }))}
            size="small"
            displayEmpty
            sx={{
              bgcolor: 'rgba(255,255,255,0.05)',
              borderRadius: '6px',
              color: '#e8eaed',
              fontSize: '0.9rem',
              '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.14)' },
              '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.28)' },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#1976d2', borderWidth: '1px' },
              '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.45)' },
            }}
            MenuProps={{ PaperProps: { sx: { bgcolor: '#1a1d27', color: '#e8eaed', border: '1px solid rgba(255,255,255,0.12)' } } }}
          >
            <MenuItem value="">Use global setting (.env)</MenuItem>
            <MenuItem value="prefetch">Prefetch — run search before LLM call</MenuItem>
            <MenuItem value="tool_call">Tool call — LLM drives searches (multi-round)</MenuItem>
          </Select>
        </Field>

        {searchModeValue === 'prefetch' && (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.search_enabled}
                    onChange={(e) => setForm((f) => ({ ...f, search_enabled: e.target.checked }))}
                    size="small"
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': { color: '#1976d2' },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#1976d2' },
                    }}
                  />
                }
                label={
                  <Typography sx={{ color: '#cdd1d9', fontSize: '0.875rem', fontWeight: 500 }}>
                    Enable Search
                  </Typography>
                }
                sx={{ ml: 0, mr: 0 }}
              />
              <InfoTooltip content={enableSearchTooltip} />
            </Box>

            {form.search_enabled && (
              <Field label="Search Query Template" tooltip={queryTemplateTooltip}>
                <TextField
                  placeholder="{ticker} pre-market price short interest today"
                  value={form.search_query_template}
                  onChange={set('search_query_template')}
                  fullWidth
                  size="small"
                  helperText="Use {ticker} as a placeholder — it will be replaced with the stock symbol at runtime"
                  FormHelperTextProps={{ sx: { color: 'rgba(255,255,255,0.35)', fontSize: '0.78rem', ml: 0 } }}
                  sx={inputSx}
                />
              </Field>
            )}
          </>
        )}

        {error && (
          <Typography sx={{ color: '#f44336', fontSize: '0.85rem' }}>{error}</Typography>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3, pt: 1, gap: 1, justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving}
          sx={{
            borderRadius: 1.5,
            px: 3,
            bgcolor: '#1976d2',
            textTransform: 'none',
            fontWeight: 600,
            '&:hover': { bgcolor: '#1565c0' },
          }}
        >
          {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Prompt'}
        </Button>
        <Button
          onClick={onClose}
          disabled={saving}
          sx={{ color: 'rgba(255,255,255,0.6)', textTransform: 'none', '&:hover': { bgcolor: 'transparent', color: '#fff' } }}
        >
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  )
}
