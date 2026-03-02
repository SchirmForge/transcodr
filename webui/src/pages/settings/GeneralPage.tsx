import { useState } from 'react'
import { useTheme, type Theme } from '../../contexts/ThemeContext'
import { useReloadConfig } from '../../hooks/useConfig'

const themeOptions: { value: Theme; label: string; icon: string }[] = [
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'system', label: 'System', icon: '💻' },
]

export function GeneralPage() {
  const { theme, setTheme } = useTheme()
  const reloadConfig = useReloadConfig()
  const [reloadMessage, setReloadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const handleReload = () => {
    setReloadMessage(null)
    reloadConfig.mutate(undefined, {
      onSuccess: () => setReloadMessage({ type: 'success', text: 'Configuration reloaded.' }),
      onError: (err) => setReloadMessage({ type: 'error', text: err instanceof Error ? err.message : 'Reload failed.' }),
    })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">General Settings</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Appearance and configuration management.</p>

      <div className="space-y-6">

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Appearance</h2>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Theme</label>
            <div className="flex gap-2">
              {themeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTheme(option.value)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                    theme === option.value
                      ? 'bg-zinc-200 text-graphite-950 dark:bg-zinc-600 dark:text-graphite-300'
                      : 'bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
                  }`}
                >
                  <span>{option.icon}</span>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Configuration</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Reload config.yaml, profiles, and watchfolders from disk without restarting the daemon.
          </p>
          {reloadMessage && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              reloadMessage.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
                : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
            }`}>
              {reloadMessage.text}
            </div>
          )}
          <button
            onClick={handleReload}
            disabled={reloadConfig.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {reloadConfig.isPending ? 'Reloading…' : 'Reload Configuration'}
          </button>
        </div>

      </div>
    </div>
  )
}
