import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/layout/Layout'
import { ActivityPage } from './pages/jobs/ActivityPage'
import { HistoryPage } from './pages/jobs/HistoryPage'
import { WatchfoldersPage } from './pages/WatchfoldersPage'
import { ProfilesPage } from './pages/ProfilesPage'
import { GeneralPage } from './pages/settings/GeneralPage'
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
            <Route path="/jobs/activity" element={<ActivityPage />} />
            <Route path="/jobs/history" element={<HistoryPage />} />
            <Route path="/watchfolders" element={<WatchfoldersPage />} />
            <Route path="/profiles" element={<ProfilesPage />} />
            <Route path="/settings/general" element={<GeneralPage />} />
            <Route path="/system/status" element={<StatusPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
