import { useState, useEffect } from 'react'
import { useConfig, useUpdateConfig } from '../../hooks/useConfig'

export function LoggingPage() {
  const { data: config, isLoading, isError, error } = useConfig()
  const updateConfig = useUpdateConfig()

  const [form, setForm] = useState({
    level: 'INFO',
    dir: '' as string,
    rotation: 'daily',
    per_job_logs: true,
  })
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (config) {
      setForm({
        level: config.logging.level,
        dir: config.logging.dir ?? '',
        rotation: config.logging.rotation,
        per_job_logs: config.logging.per_job_logs,
      })
      setDirty(false)
    }
  }, [config])

  const handleChange = (field: string, value: string | boolean) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setDirty(true)
    setMessage(null)
  }

  const handleSave = () => {
    updateConfig.mutate(
      {
        logging: {
          level: form.level,
          dir: form.dir || null,
          rotation: form.rotation,
          per_job_logs: form.per_job_logs,
        },
      },
      {
        onSuccess: (data) => {
          setDirty(false)
          const warnings = data.warnings?.length ? ` (${data.warnings.join('; ')})` : ''
          setMessage({ type: 'success', text: `Configuration saved.${warnings}` })
        },
        onError: (err) => {
          setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to save' })
        },
      }
    )
  }

  const handleCancel = () => {
    if (config) {
      setForm({
        level: config.logging.level,
        dir: config.logging.dir ?? '',
        rotation: config.logging.rotation,
        per_job_logs: config.logging.per_job_logs,
      })
      setDirty(false)
      setMessage(null)
    }
  }

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Logging Settings</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Logging Settings</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">
            Failed to load configuration: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Logging Settings</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Configure log level, file logging, and rotation.</p>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
            : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
        }`}>
          {message.text}
        </div>
      )}

      <div className="space-y-6">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Log Level</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Level</label>
            <select
              value={form.level}
              onChange={e => handleChange('level', e.target.value)}
              className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
            >
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Controls verbosity of daemon logs. INFO is recommended for normal use.</p>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">File Logging</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Log Directory</label>
              <input
                type="text"
                value={form.dir}
                onChange={e => handleChange('dir', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                placeholder="Leave empty for no file logging"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Directory for log files. Leave empty to disable file logging.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Rotation</label>
              <select
                value={form.rotation}
                onChange={e => handleChange('rotation', e.target.value)}
                className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="size">Size-based</option>
              </select>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Log file rotation policy.</p>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Per-Job Logs</label>
                <p className="text-xs text-gray-500 dark:text-gray-400">Create a separate log file for each encoding job.</p>
              </div>
              <button
                onClick={() => handleChange('per_job_logs', !form.per_job_logs)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.per_job_logs ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  form.per_job_logs ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={handleSave}
          disabled={!dirty || updateConfig.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {updateConfig.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleCancel}
          disabled={!dirty}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
