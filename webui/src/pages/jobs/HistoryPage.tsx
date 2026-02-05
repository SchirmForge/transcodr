import { useHistoryJobs, useRetryJob } from '../../hooks/useJobs'
import { useClearCompleted, useClearFailed } from '../../hooks/useQueue'
import type { JobInfo } from '../../api/types'

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800'
    case 'failed':
      return 'bg-red-100 text-red-800'
    case 'cancelled':
      return 'bg-gray-100 text-gray-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString()
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function HistoryJobCard({ job, onRetry }: { job: JobInfo; onRetry: () => void }) {
  const filename = job.source_path.split('/').pop() || job.source_path

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between items-start mb-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium text-gray-900 truncate" title={job.source_path}>
            {filename}
          </h3>
          <p className="text-sm text-gray-500">
            Profile: {job.profile}
            {job.total_profiles > 1 && ` (${job.profile_index + 1}/${job.total_profiles})`}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(job.status)}`}>
            {job.status}
          </span>
          {job.status === 'failed' && (
            <button
              onClick={onRetry}
              className="px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      </div>

      <div className="mt-2 text-sm text-gray-500 space-y-1">
        <div className="flex justify-between">
          <span>Completed:</span>
          <span>{formatDate(job.completed_at)}</span>
        </div>
        {job.status === 'completed' && job.output_size_bytes > 0 && (
          <div className="flex justify-between">
            <span>Output size:</span>
            <span>{formatBytes(job.output_size_bytes)}</span>
          </div>
        )}
        {job.status === 'failed' && job.error_message && (
          <div className="mt-2 p-2 bg-red-50 rounded text-red-700 text-xs">
            {job.error_message}
          </div>
        )}
      </div>
    </div>
  )
}

export function HistoryPage() {
  const { data: jobs, isLoading, isError } = useHistoryJobs()
  const retryMutation = useRetryJob()
  const clearCompletedMutation = useClearCompleted()
  const clearFailedMutation = useClearFailed()

  const completedCount = jobs?.filter(j => j.status === 'completed').length || 0
  const failedCount = jobs?.filter(j => j.status === 'failed').length || 0

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs History</h1>
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs History</h1>
        <div className="mt-6 p-4 bg-red-50 rounded-lg shadow border border-red-200">
          <p className="text-red-600 text-sm">Failed to load jobs</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs History</h1>
          <p className="text-gray-600">Completed and failed jobs.</p>
        </div>
        <div className="flex gap-2">
          {completedCount > 0 && (
            <button
              onClick={() => clearCompletedMutation.mutate()}
              disabled={clearCompletedMutation.isPending}
              className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded transition-colors disabled:opacity-50"
            >
              Clear Completed ({completedCount})
            </button>
          )}
          {failedCount > 0 && (
            <button
              onClick={() => clearFailedMutation.mutate()}
              disabled={clearFailedMutation.isPending}
              className="px-3 py-1.5 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded transition-colors disabled:opacity-50"
            >
              Clear Failed ({failedCount})
            </button>
          )}
        </div>
      </div>

      {jobs && jobs.length > 0 ? (
        <div className="space-y-4">
          {jobs.map((job) => (
            <HistoryJobCard
              key={job.id}
              job={job}
              onRetry={() => retryMutation.mutate(job.id)}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">No job history</p>
        </div>
      )}
    </div>
  )
}
