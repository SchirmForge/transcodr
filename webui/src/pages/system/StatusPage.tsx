import { useStatus } from '../../hooks/useStatus'

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

export function StatusPage() {
  const { data: status, isLoading, isError, error } = useStatus()

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">System Status</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">System Status</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">
            Failed to connect to daemon: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  if (!status) return null

  const vaapiAvailable = Boolean(status.hardware.vaapi_available ?? status.hardware.vaapi)
  const nvencAvailable = Boolean(status.hardware.nvenc_available ?? status.hardware.nvidia_nvenc)
  const qsvAvailable = Boolean(status.hardware.qsv_available ?? status.hardware.intel_qsv)

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">System Status</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Daemon status and system information.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Daemon Info */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Daemon</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Status</dt>
              <dd className={status.running ? 'text-green-600 dark:text-green-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                {status.running ? 'Running' : 'Stopped'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Version</dt>
              <dd className="text-gray-900 dark:text-gray-100">{status.version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Uptime</dt>
              <dd className="text-gray-900 dark:text-gray-100">{formatUptime(status.uptime_seconds)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Config</dt>
              <dd className="text-gray-900 dark:text-gray-100 truncate max-w-32" title={status.config_path}>
                {status.config_path.split('/').pop()}
              </dd>
            </div>
          </dl>
        </div>

        {/* Queue Info */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Queue</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Status</dt>
              <dd className={status.queue.paused ? 'text-yellow-600 dark:text-yellow-400 font-medium' : 'text-green-600 dark:text-green-400 font-medium'}>
                {status.queue.paused ? 'Paused' : 'Active'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Running</dt>
              <dd className="text-gray-900 dark:text-gray-100">{status.queue.running_jobs} / {status.queue.max_concurrent}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Pending</dt>
              <dd className="text-gray-900 dark:text-gray-100">{status.queue.pending_jobs}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Completed</dt>
              <dd className="text-gray-900 dark:text-gray-100">{status.queue.completed_jobs}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Failed</dt>
              <dd className={status.queue.failed_jobs > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}>
                {status.queue.failed_jobs}
              </dd>
            </div>
          </dl>
        </div>

        {/* Hardware Info */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Hardware</h2>
          <dl className="space-y-2 text-sm">
            {status.hardware.cpu_model && (
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500 dark:text-gray-400">CPU</dt>
                <dd className="text-gray-900 dark:text-gray-100 truncate" title={status.hardware.cpu_model}>
                  {status.hardware.cpu_model}
                </dd>
              </div>
            )}
            {status.hardware.cpu_count && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Cores</dt>
                <dd className="text-gray-900 dark:text-gray-100">{status.hardware.cpu_count}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">VAAPI</dt>
              <dd className={vaapiAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                {vaapiAvailable ? 'Available' : 'Not available'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">NVENC</dt>
              <dd className={nvencAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                {nvencAvailable ? 'Available' : 'Not available'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">QuickSync</dt>
              <dd className={qsvAvailable ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
                {qsvAvailable ? 'Available' : 'Not available'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
        <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Raw /status JSON</h2>
        <pre className="text-xs text-gray-800 dark:text-gray-100 bg-gray-50 dark:bg-gray-900/40 p-3 rounded overflow-auto max-h-96">
          {JSON.stringify(status, null, 2)}
        </pre>
      </div>

      {/* Watch Folders Summary */}
      {status.watch_folders && status.watch_folders.length > 0 && (
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Active Watch Folders</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {status.watch_folders.length} watch folder{status.watch_folders.length !== 1 ? 's' : ''} configured
          </p>
        </div>
      )}
    </div>
  )
}
