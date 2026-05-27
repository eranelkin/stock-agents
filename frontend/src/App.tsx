import { useState } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
import theme from './theme'
import Header from './components/Header'
import RunPage from './pages/RunPage'
import ModelsPage from './pages/ModelsPage'

export type TabId = 'run' | 'models'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('run')

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
        <Header activeTab={activeTab} onTabChange={setActiveTab} />
        <Box component="main" sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'run' && <RunPage />}
          {activeTab === 'models' && <ModelsPage />}
        </Box>
      </Box>
    </ThemeProvider>
  )
}

export default App
