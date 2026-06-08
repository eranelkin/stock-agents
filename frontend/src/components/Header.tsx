import { useEffect, useRef, useState } from 'react'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Popover from '@mui/material/Popover'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import { fetchModels } from '../api/models'
import type { Model } from '../types/model'
import { type TabId } from '../App'

interface HeaderProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  selectedModelIds: string[]
  onSelectedModelsChange: (ids: string[]) => void
  refreshKey: number
  modelsDisabled?: boolean
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'run', label: 'Run' },
  { id: 'prompts', label: 'Prompts' },
  { id: 'chat', label: 'Chat' },
  { id: 'models', label: 'Models' },
]

export default function Header({
  activeTab,
  onTabChange,
  selectedModelIds,
  onSelectedModelsChange,
  refreshKey,
  modelsDisabled = false,
}: HeaderProps) {
  const [activeModels, setActiveModels] = useState<Model[]>([])
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchModels(true)
      .then(setActiveModels)
      .catch(() => setActiveModels([]))
  }, [refreshKey])

  // Remove selected ids that no longer exist in active models (skip while models haven't loaded yet)
  useEffect(() => {
    if (activeModels.length === 0) return
    const activeIds = new Set(activeModels.map((m) => m.id))
    const valid = selectedModelIds.filter((id) => activeIds.has(id))
    if (valid.length !== selectedModelIds.length) onSelectedModelsChange(valid)
  }, [activeModels])

  const currentIndex = TABS.findIndex((t) => t.id === activeTab)
  const open = Boolean(anchorEl)

  const handleTriggerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (modelsDisabled) return
    setAnchorEl(e.currentTarget)
  }

  const handleClose = () => setAnchorEl(null)

  const toggleModel = (id: string) => {
    onSelectedModelsChange(
      selectedModelIds.includes(id)
        ? selectedModelIds.filter((x) => x !== id)
        : [...selectedModelIds, id]
    )
  }

  const selectedModels = activeModels.filter((m) => selectedModelIds.includes(m.id))

  return (
    <AppBar position="sticky">
      <Toolbar sx={{ gap: 3, minHeight: '56px !important' }}>
        <Typography
          variant="subtitle1"
          fontWeight={700}
          sx={{ color: 'text.primary', letterSpacing: 0.5, whiteSpace: 'nowrap' }}
        >
          Stock Agents
        </Typography>

        <Tabs
          value={currentIndex}
          onChange={(_, idx: number) => onTabChange(TABS[idx].id)}
          TabIndicatorProps={{ style: { backgroundColor: '#1976d2', height: 3 } }}
          sx={{ minHeight: 56 }}
        >
          {TABS.map((tab) => (
            <Tab
              key={tab.id}
              label={tab.label}
              sx={{
                minHeight: 56,
                textTransform: 'none',
                fontWeight: 500,
                fontSize: '0.9rem',
                color: 'text.secondary',
                px: 2.5,
                borderRadius: 1,
                mx: 0.25,
                '&.Mui-selected': { color: '#1976d2', backgroundColor: 'rgba(25, 118, 210, 0.15)' },
                '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.05)' },
              }}
            />
          ))}
        </Tabs>

        <Box sx={{ flex: 1 }} />

        {/* Market Overview icon button */}
        <Tooltip title="Market Overview">
          <IconButton
            onClick={() => onTabChange('market')}
            size="small"
            sx={{
              color: activeTab === 'market' ? '#ff9800' : 'text.secondary',
              bgcolor: activeTab === 'market' ? 'rgba(255,152,0,0.12)' : 'transparent',
              border: activeTab === 'market' ? '1px solid rgba(255,152,0,0.3)' : '1px solid rgba(255,255,255,0.08)',
              borderRadius: 1,
              width: 36,
              height: 36,
              '&:hover': { bgcolor: 'rgba(255,152,0,0.1)', color: '#ff9800' },
            }}
          >
            <SentimentGaugeIcon active={activeTab === 'market'} />
          </IconButton>
        </Tooltip>

        {/* Model multi-select trigger */}
        <Box
          ref={triggerRef}
          onClick={handleTriggerClick}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            minWidth: 200,
            maxWidth: 420,
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
            border: '1px solid rgba(255,255,255,0.12)',
            bgcolor: 'rgba(255,255,255,0.04)',
            cursor: modelsDisabled ? 'not-allowed' : 'pointer',
            flexWrap: 'wrap',
            opacity: modelsDisabled ? 0.45 : 1,
            '&:hover': { bgcolor: modelsDisabled ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.08)' },
          }}
        >
          {selectedModels.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              Select models…
            </Typography>
          ) : (
            selectedModels.map((m) => (
              <Chip
                key={m.id}
                label={m.name}
                size="small"
                onDelete={(e) => { e.stopPropagation(); toggleModel(m.id) }}
                sx={{ bgcolor: 'rgba(25,118,210,0.2)', color: '#90caf9', fontSize: '0.75rem' }}
              />
            ))
          )}
          <KeyboardArrowDownIcon
            sx={{
              ml: 'auto',
              color: 'text.secondary',
              fontSize: 18,
              transition: 'transform 0.2s',
              transform: open ? 'rotate(180deg)' : 'none',
            }}
          />
        </Box>

        {/* ── Popover ── */}
        <Popover
          open={open}
          anchorEl={anchorEl}
          onClose={handleClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          slotProps={{
            paper: {
              sx: {
                bgcolor: '#1a1a1a',
                border: '1px solid rgba(255,255,255,0.1)',
                minWidth: 260,
                mt: 0.5,
              },
            },
          }}
        >
          <List dense disablePadding>
            {activeModels.length === 0 && (
              <ListItemButton disabled>
                <ListItemText
                  primary="No active models"
                  primaryTypographyProps={{ style: { color: '#666', fontSize: '0.85rem' } }}
                />
              </ListItemButton>
            )}
            {activeModels.map((model) => {
              const selected = selectedModelIds.includes(model.id)
              return (
                <ListItemButton
                  key={model.id}
                  onClick={() => toggleModel(model.id)}
                  sx={{
                    px: 2,
                    py: 1,
                    bgcolor: selected ? 'rgba(255,255,255,0.08)' : 'transparent',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.12)' },
                  }}
                >
                  <ListItemText
                    primary={model.name}
                    primaryTypographyProps={{
                      style: {
                        fontSize: '0.875rem',
                        color: selected ? '#9e9e9e' : '#ffffff',
                      },
                    }}
                  />
                </ListItemButton>
              )
            })}
          </List>
        </Popover>
      </Toolbar>
    </AppBar>
  )
}

function SentimentGaugeIcon({ active }: { active: boolean }) {
  const color = active ? '#ff9800' : 'currentColor'
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Gauge arc */}
      <path d="M5 17A7 7 0 0 1 19 17" />
      {/* Tick marks */}
      <line x1="12" y1="10" x2="12" y2="8" />
      <line x1="7.5" y1="11.5" x2="6.1" y2="10.1" />
      <line x1="16.5" y1="11.5" x2="17.9" y2="10.1" />
      {/* Needle pointing slightly right (greed side) */}
      <line x1="12" y1="17" x2="16" y2="13" strokeWidth="2" />
      {/* Center dot */}
      <circle cx="12" cy="17" r="1.2" fill={color} stroke="none" />
    </svg>
  )
}
