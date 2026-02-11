import { useState, useEffect } from 'react'
import { useConfig, useUpdateConfig } from '../../hooks/useConfig'
import { useStatus } from '../../hooks/useStatus'

export function EncodingPage() {
  const { data: config, isLoading, isError, error } = useConfig()
  const { data: status } = useStatus()
  const updateConfig = useUpdateConfig()

  const [form, setForm] = useState({
    hardware_accel: 'auto',
    binary_path: 'ffmpeg',
    duration_tolerance: 5.0,
  })
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (config) {
      setForm({
        hardware_accel: config.ffmpeg.hardware_accel,
        binary_path: config.ffmpeg.binary_path,
        duration_tolerance: config.validation.duration_tolerance,
      })
      setDirty(false)
    }
  }, [config])

  const handleChange = (field: string, value: string | number) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setDirty(true)
    setMessage(null)
  }

  const handleSave = () => {
    updateConfig.mutate(
      {
        ffmpeg: {
          hardware_accel: form.hardware_accel,
          binary_path: form.binary_path,
        },
        validation: {
          duration_tolerance: form.duration_tolerance,
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
        hardware_accel: config.ffmpeg.hardware_accel,
        binary_path: config.ffmpeg.binary_path,
        duration_tolerance: config.validation.duration_tolerance,
      })
      setDirty(false)
      setMessage(null)
    }
  }

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Encoding Settings</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Encoding Settings</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">
            Failed to load configuration: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  const vaapiAvailable = status ? Boolean(status.hardware.vaapi_available ?? status.hardware.vaapi) : false
  const nvencAvailable = status ? Boolean(status.hardware.nvenc_available ?? status.hardware.nvidia_nvenc) : false
  const qsvAvailable = status ? Boolean(status.hardware.qsv_available ?? status.hardware.intel_qsv) : false

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Encoding Settings</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Configure FFmpeg, hardware acceleration, and validation.</p>

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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">FFmpeg</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Binary Path</label>
              <input
                type="text"
                value={form.binary_path}
                onChange={e => handleChange('binary_path', e.target.value)}
                className="w-64 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                placeholder="ffmpeg"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Path to FFmpeg binary. Use "ffmpeg" if it's in PATH.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Hardware Acceleration</label>
              <select
                value={form.hardware_accel}
                onChange={e => handleChange('hardware_accel', e.target.value)}
                className="w-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              >
                <option value="auto">Auto-detect</option>
                <option value="vaapi">VAAPI (AMD/Intel)</option>
                <option value="nvenc">NVENC (NVIDIA)</option>
                <option value="qsv">QuickSync (Intel)</option>
                <option value="none">None (CPU only)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">"Auto" detects available hardware at runtime.</p>
            </div>
          </div>

          {status && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Detected Hardware</h3>
              <div className="flex gap-4 text-sm">
                <span className={vaapiAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                  VAAPI: {vaapiAvailable ? 'Available' : 'Not available'}
                </span>
                <span className={nvencAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                  NVENC: {nvencAvailable ? 'Available' : 'Not available'}
                </span>
                <span className={qsvAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                  QSV: {qsvAvailable ? 'Available' : 'Not available'}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Validation</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Duration Tolerance (seconds)</label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={form.duration_tolerance}
              onChange={e => handleChange('duration_tolerance', parseFloat(e.target.value) || 0)}
              className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Allowed duration difference for extracted clips. Set 0 to disable check.</p>
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
