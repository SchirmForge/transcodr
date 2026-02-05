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
        <h1 className="text-2xl font-bold text-gray-900 mb-4">System Status</h1>
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">System Status</h1>
        <div className="mt-6 p-4 bg-red-50 rounded-lg shadow border border-red-200">
          <p className="text-red-600 text-sm">
            Failed to connect to daemon: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  if (!status) return null

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">System Status</h1>
      <p className="text-gray-600 mb-6">Daemon status and system information.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Daemon Info */}
        <div className="p-4 bg-white rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 mb-3">Daemon</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Status</dt>
              <dd className={status.running ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                {status.running ? 'Running' : 'Stopped'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Version</dt>
              <dd className="text-gray-900">{status.version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Uptime</dt>
              <dd className="text-gray-900">{formatUptime(status.uptime_seconds)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Config</dt>
              <dd className="text-gray-900 truncate max-w-32" title={status.config_path}>
                {status.config_path.split('/').pop()}
              </dd>
            </div>
          </dl>
        </div>

        {/* Queue Info */}
        <div className="p-4 bg-white rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 mb-3">Queue</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Status</dt>
              <dd className={status.queue.paused ? 'text-yellow-600 font-medium' : 'text-green-600 font-medium'}>
                {status.queue.paused ? 'Paused' : 'Active'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Running</dt>
              <dd className="text-gray-900">{status.queue.running_jobs} / {status.queue.max_concurrent}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Pending</dt>
              <dd className="text-gray-900">{status.queue.pending_jobs}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Completed</dt>
              <dd className="text-gray-900">{status.queue.completed_jobs}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Failed</dt>
              <dd className={status.queue.failed_jobs > 0 ? 'text-red-600' : 'text-gray-900'}>
                {status.queue.failed_jobs}
              </dd>
            </div>
          </dl>
        </div>

        {/* Hardware Info */}
        <div className="p-4 bg-white rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 mb-3">Hardware Acceleration</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">VAAPI (AMD/Intel)</dt>
              <dd className={status.hardware.vaapi_available ? 'text-green-600' : 'text-gray-400'}>
                {status.hardware.vaapi_available ? 'Available' : 'Not available'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">NVENC (NVIDIA)</dt>
              <dd className={status.hardware.nvenc_available ? 'text-green-600' : 'text-gray-400'}>
                {status.hardware.nvenc_available ? 'Available' : 'Not available'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">QuickSync (Intel)</dt>
              <dd className={status.hardware.qsv_available ? 'text-green-600' : 'text-gray-400'}>
                {status.hardware.qsv_available ? 'Available' : 'Not available'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Watch Folders Summary */}
      {status.watch_folders && status.watch_folders.length > 0 && (
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <h2 className="font-semibold text-gray-800 mb-3">Active Watch Folders</h2>
          <p className="text-sm text-gray-600">
            {status.watch_folders.length} watch folder{status.watch_folders.length !== 1 ? 's' : ''} configured
          </p>
        </div>
      )}
    </div>
  )
}
