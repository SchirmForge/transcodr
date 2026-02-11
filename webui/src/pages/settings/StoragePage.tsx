import { useState, useEffect } from 'react'
import { useConfig, useUpdateConfig } from '../../hooks/useConfig'

export function StoragePage() {
  const { data: config, isLoading, isError, error } = useConfig()
  const updateConfig = useUpdateConfig()

  const [form, setForm] = useState({
    root_media: '',
    temp_dir: '',
    backup_originals: true,
    backup_dir: '',
    min_free_space_gb: 10,
    on_extension_mismatch: 'rename',
    profile_name_separator: '_',
  })
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (config) {
      setForm({
        root_media: config.storage.root_media,
        temp_dir: config.storage.temp_dir,
        backup_originals: config.storage.backup_originals,
        backup_dir: config.storage.backup_dir,
        min_free_space_gb: config.storage.min_free_space_gb,
        on_extension_mismatch: config.storage.on_extension_mismatch,
        profile_name_separator: config.storage.profile_name_separator,
      })
      setDirty(false)
    }
  }, [config])

  const handleChange = (field: string, value: string | number | boolean) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setDirty(true)
    setMessage(null)
  }

  const handleSave = () => {
    updateConfig.mutate(
      { storage: form },
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
        root_media: config.storage.root_media,
        temp_dir: config.storage.temp_dir,
        backup_originals: config.storage.backup_originals,
        backup_dir: config.storage.backup_dir,
        min_free_space_gb: config.storage.min_free_space_gb,
        on_extension_mismatch: config.storage.on_extension_mismatch,
        profile_name_separator: config.storage.profile_name_separator,
      })
      setDirty(false)
      setMessage(null)
    }
  }

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Storage Settings</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Storage Settings</h1>
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
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Storage Settings</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Configure media paths, temp directory, and backup options.</p>

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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Paths</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Root Media</label>
              <input
                type="text"
                value={form.root_media}
                onChange={e => handleChange('root_media', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                placeholder="/path/to/media"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Base path for $root_media placeholder. Supports ~ and $HOME.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Temp Directory</label>
              <input
                type="text"
                value={form.temp_dir}
                onChange={e => handleChange('temp_dir', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                placeholder="/tmp/transcodr"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Temporary directory for encoding. Use fast storage (SSD) for best performance.</p>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Backup</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Backup Originals</label>
                <p className="text-xs text-gray-500 dark:text-gray-400">Create backup of original files before replacing.</p>
              </div>
              <button
                onClick={() => handleChange('backup_originals', !form.backup_originals)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.backup_originals ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  form.backup_originals ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Backup Directory</label>
              <input
                type="text"
                value={form.backup_dir}
                onChange={e => handleChange('backup_dir', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                placeholder="./.originals"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Relative to source file or absolute path.</p>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Space & Output</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Min Free Space (GB)</label>
              <input
                type="number"
                min={1}
                value={form.min_free_space_gb}
                onChange={e => handleChange('min_free_space_gb', parseInt(e.target.value) || 1)}
                className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Minimum free disk space required before starting a job.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Extension Mismatch Policy</label>
              <select
                value={form.on_extension_mismatch}
                onChange={e => handleChange('on_extension_mismatch', e.target.value)}
                className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              >
                <option value="rename">Rename (correct extension)</option>
                <option value="reject">Reject (fail job)</option>
                <option value="keep">Keep (source extension)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">What to do when source extension differs from profile container in replace mode.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Profile Name Separator</label>
              <input
                type="text"
                value={form.profile_name_separator}
                onChange={e => handleChange('profile_name_separator', e.target.value)}
                className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                maxLength={5}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Separator between filename and profile name for append_profile_name.</p>
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
