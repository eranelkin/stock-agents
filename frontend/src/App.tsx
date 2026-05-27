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
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([])
  const [modelsRefreshKey, setModelsRefreshKey] = useState(0)

  const refreshModels = () => setModelsRefreshKey((k) => k + 1)

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
        <Header
          activeTab={activeTab}
          onTabChange={setActiveTab}
          selectedModelIds={selectedModelIds}
          onSelectedModelsChange={setSelectedModelIds}
          refreshKey={modelsRefreshKey}
        />
        <Box component="main" sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'run' && <RunPage selectedModelIds={selectedModelIds} />}
          {activeTab === 'models' && <ModelsPage onModelsChange={refreshModels} />}
        </Box>
      </Box>
    </ThemeProvider>
  )
}

export default App
