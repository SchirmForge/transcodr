import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import iconImg from '../../assets/transcodr-icon.png'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-steel-50 dark:bg-graphite-950 lg:flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 min-w-0">
        <header className="lg:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3 bg-steel-50/95 dark:bg-graphite-950/95 backdrop-blur border-b border-graphite-200 dark:border-graphite-800">
          <button
            onClick={() => setSidebarOpen(true)}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg bg-graphite-200 text-steel-800 dark:bg-graphite-800 dark:text-steel-100"
          >
            Menu
          </button>
          <img src={iconImg} alt="Transcodr" className="h-7 w-7" />
        </header>

        <main className="p-4 lg:p-6 overflow-auto">
        <Outlet />
        </main>
      </div>
    </div>
  )
}
