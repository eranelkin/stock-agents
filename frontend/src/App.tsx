import { useState } from 'react'
import { useLocalStorage } from './hooks/useLocalStorage'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
import theme from './theme'
import Header from './components/Header'
import RunPage from './pages/RunPage'
import ModelsPage from './pages/ModelsPage'
import PromptsPage from './pages/PromptsPage'
import ChatPage from './pages/ChatPage'

export type TabId = 'run' | 'prompts' | 'chat' | 'models'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('run')
  const [selectedModelIds, setSelectedModelIds] = useLocalStorage<string[]>('selectedModelIds', [])
  const [modelsRefreshKey, setModelsRefreshKey] = useState(0)
  const [pendingChatInput, setPendingChatInput] = useState<string | null>(null)
  const [runInProgress, setRunInProgress] = useState(false)

  const refreshModels = () => setModelsRefreshKey((k) => k + 1)

  const handleRunPrompt = (content: string) => {
    setPendingChatInput(content)
    setActiveTab('chat')
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ height: '100vh', overflow: 'hidden', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
        <Header
          activeTab={activeTab}
          onTabChange={setActiveTab}
          selectedModelIds={selectedModelIds}
          onSelectedModelsChange={setSelectedModelIds}
          refreshKey={modelsRefreshKey}
          modelsDisabled={runInProgress}
        />
        <Box component="main" sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'run' && <RunPage selectedModelIds={selectedModelIds} onRunActiveChange={setRunInProgress} />}
          {activeTab === 'prompts' && <PromptsPage onRunPrompt={handleRunPrompt} />}
          {activeTab === 'chat' && <ChatPage selectedModelIds={selectedModelIds} pendingInput={pendingChatInput} onClearPendingInput={() => setPendingChatInput(null)} />}
          {activeTab === 'models' && <ModelsPage onModelsChange={refreshModels} />}
        </Box>
      </Box>
    </ThemeProvider>
  )
}

export default App
