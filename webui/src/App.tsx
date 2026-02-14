import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/layout/Layout'
import { ActivityPage } from './pages/jobs/ActivityPage'
import { CreateJobPage } from './pages/jobs/CreateJobPage'
import { HistoryPage } from './pages/jobs/HistoryPage'
import { RulesExplained } from './pages/encoding-rules/RulesExplained'
import { WatchfoldersPage } from './pages/encoding-rules/WatchfoldersPage'
import { ProfilesPage } from './pages/encoding-rules/ProfilesPage'
import { GeneralPage } from './pages/settings/GeneralPage'
import { StoragePage } from './pages/settings/StoragePage'
import { EncodingPage } from './pages/settings/EncodingPage'
import { DaemonPage } from './pages/settings/DaemonPage'
import { LoggingPage } from './pages/settings/LoggingPage'
import { StatusPage } from './pages/system/StatusPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchInterval: 10000,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/jobs/activity" replace />} />
            <Route path="/jobs" element={<Navigate to="/jobs/activity" replace />} />
            <Route path="/jobs/activity" element={<ActivityPage />} />
            <Route path="/jobs/create" element={<CreateJobPage />} />
            <Route path="/jobs/history" element={<HistoryPage />} />
            <Route path="/encoding-rules" element={<Navigate to="/encoding-rules/rules-explained" replace />} />
            <Route path="/encoding-rules/rules-explained" element={<RulesExplained />} />
            <Route path="/encoding-rules/watchfolders" element={<WatchfoldersPage />} />
            <Route path="/encoding-rules/profiles" element={<ProfilesPage />} />
            <Route path="/settings" element={<Navigate to="/settings/general" replace />} />
            <Route path="/settings/general" element={<GeneralPage />} />
            <Route path="/settings/storage" element={<StoragePage />} />
            <Route path="/settings/encoding" element={<EncodingPage />} />
            <Route path="/settings/daemon" element={<DaemonPage />} />
            <Route path="/settings/logging" element={<LoggingPage />} />
            <Route path="/system/status" element={<StatusPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
