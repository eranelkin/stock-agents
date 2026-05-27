import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Box from '@mui/material/Box'
import { type TabId } from '../App'

interface HeaderProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'run', label: 'Run' },
  { id: 'models', label: 'Models' },
]

export default function Header({ activeTab, onTabChange }: HeaderProps) {
  const currentIndex = TABS.findIndex((t) => t.id === activeTab)

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
          TabIndicatorProps={{
            style: { backgroundColor: '#1976d2', height: 3 },
          }}
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
                '&.Mui-selected': {
                  color: '#1976d2',
                  backgroundColor: 'rgba(25, 118, 210, 0.15)',
                },
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.05)',
                },
              }}
            />
          ))}
        </Tabs>

        <Box sx={{ flex: 1 }} />
      </Toolbar>
    </AppBar>
  )
}
