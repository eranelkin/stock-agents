import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import TextField from '@mui/material/TextField'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import CloseIcon from '@mui/icons-material/Close'
import { createPrompt, updatePrompt } from '../api/prompts'
import type { Prompt } from '../types/prompt'

interface PromptDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
  editPrompt?: Prompt | null
  defaultCategory: string
}

const EMPTY = { title: '', content: '' }

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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      <Typography sx={{ color: '#cdd1d9', fontWeight: 500, fontSize: '0.875rem' }}>
        {label}
      </Typography>
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
      setForm({ title: editPrompt.title, content: editPrompt.content })
    } else {
      setForm(EMPTY)
    }
    setError(null)
  }, [editPrompt, open])

  const set =
    (field: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.content.trim()) {
      setError('Title and Prompt are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      if (isEdit && editPrompt) {
        await updatePrompt(editPrompt.id, { title: form.title, content: form.content })
      } else {
        await createPrompt({ title: form.title, content: form.content, category: defaultCategory })
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
