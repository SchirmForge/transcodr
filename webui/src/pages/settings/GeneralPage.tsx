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

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">General Settings</h1>
          <p className="text-gray-600 dark:text-gray-400">Application settings and configuration.</p>
        </div>
        <button
          onClick={() => reloadConfig.mutate()}
          disabled={reloadConfig.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {reloadConfig.isPending ? 'Reloading…' : 'Reload Configuration'}
        </button>
      </div>

      <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
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
    </div>
  )
}
