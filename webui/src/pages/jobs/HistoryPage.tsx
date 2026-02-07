import { useState, useMemo } from 'react'
import { useHistoryJobs, useRetryJob } from '../../hooks/useJobs'
import { useClearCompleted, useClearFailed } from '../../hooks/useQueue'
import type { JobInfo } from '../../api/types'
import { FilterSelect } from '../../components/ui/FilterSelect'
import { SortSelect } from '../../components/ui/SortSelect'

const SORT_FIELD_KEY = 'transcodr-history-sort-field'
const SORT_DIR_KEY = 'transcodr-history-sort-direction'

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300'
    case 'failed':
      return 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300'
    case 'cancelled':
      return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
    default:
      return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
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
    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
      <div className="flex justify-between items-start mb-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate" title={job.source_path}>
            {filename}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
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
              className="px-2 py-1 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      </div>

      <div className="mt-2 text-sm text-gray-500 dark:text-gray-400 space-y-1">
        <div className="flex justify-between">
          <span>Completed:</span>
          <span className="text-gray-900 dark:text-gray-100">{formatDate(job.completed_at)}</span>
        </div>
        {job.status === 'completed' && job.output_size_bytes > 0 && (
          <div className="flex justify-between">
            <span>Output size:</span>
            <span className="text-gray-900 dark:text-gray-100">{formatBytes(job.output_size_bytes)}</span>
          </div>
        )}
        {job.status === 'failed' && job.error_message && (
          <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/30 rounded text-red-700 dark:text-red-300 text-xs">
            {job.error_message}
          </div>
        )}
      </div>
    </div>
  )
}

const statusOptions = [
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const sortOptions = [
  { value: 'completed_at', label: 'Date Completed' },
  { value: 'created_at', label: 'Date Created' },
  { value: 'filename', label: 'Filename' },
  { value: 'source_size_bytes', label: 'File Size' },
  { value: 'profile', label: 'Profile' },
]

export function HistoryPage() {
  const { data: jobs, isLoading, isError } = useHistoryJobs()
  const retryMutation = useRetryJob()
  const clearCompletedMutation = useClearCompleted()
  const clearFailedMutation = useClearFailed()
  const [statusFilter, setStatusFilter] = useState('')
  const [profileFilter, setProfileFilter] = useState('')
  const [sortField, setSortField] = useState(() => localStorage.getItem(SORT_FIELD_KEY) || 'completed_at')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>(() => (localStorage.getItem(SORT_DIR_KEY) as 'asc' | 'desc') || 'desc')

  // Extract unique profiles from jobs
  const profileOptions = useMemo(() => {
    if (!jobs) return []
    const profiles = [...new Set(jobs.map(j => j.profile))].sort()
    return profiles.map(p => ({ value: p, label: p }))
  }, [jobs])

  // Filter and sort jobs
  const filteredJobs = useMemo(() => {
    if (!jobs) return []
    let result = [...jobs]

    // Apply filters
    if (statusFilter) {
      result = result.filter(j => j.status === statusFilter)
    }
    if (profileFilter) {
      result = result.filter(j => j.profile === profileFilter)
    }

    // Apply sorting
    result.sort((a, b) => {
      let comparison = 0
      switch (sortField) {
        case 'completed_at':
          const aCompleted = a.completed_at ? new Date(a.completed_at).getTime() : 0
          const bCompleted = b.completed_at ? new Date(b.completed_at).getTime() : 0
          comparison = aCompleted - bCompleted
          break
        case 'created_at':
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          break
        case 'filename':
          const aName = a.source_path.split('/').pop() || ''
          const bName = b.source_path.split('/').pop() || ''
          comparison = aName.localeCompare(bName)
          break
        case 'source_size_bytes':
          comparison = a.source_size_bytes - b.source_size_bytes
          break
        case 'profile':
          comparison = a.profile.localeCompare(b.profile)
          break
      }
      return sortDirection === 'asc' ? comparison : -comparison
    })

    return result
  }, [jobs, statusFilter, profileFilter, sortField, sortDirection])

  const handleSortFieldChange = (field: string) => {
    setSortField(field)
    localStorage.setItem(SORT_FIELD_KEY, field)
  }

  const handleSortDirectionChange = (direction: 'asc' | 'desc') => {
    setSortDirection(direction)
    localStorage.setItem(SORT_DIR_KEY, direction)
  }

  const completedCount = jobs?.filter(j => j.status === 'completed').length || 0
  const failedCount = jobs?.filter(j => j.status === 'failed').length || 0

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Jobs History</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Jobs History</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">Failed to load jobs</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Jobs History</h1>
          <p className="text-gray-600 dark:text-gray-400">Completed and failed jobs.</p>
        </div>
        <div className="flex gap-2">
          {completedCount > 0 && (
            <button
              onClick={() => clearCompletedMutation.mutate()}
              disabled={clearCompletedMutation.isPending}
              className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded transition-colors disabled:opacity-50"
            >
              Clear Completed ({completedCount})
            </button>
          )}
          {failedCount > 0 && (
            <button
              onClick={() => clearFailedMutation.mutate()}
              disabled={clearFailedMutation.isPending}
              className="px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/50 hover:bg-red-200 dark:hover:bg-red-900/70 text-red-700 dark:text-red-300 rounded transition-colors disabled:opacity-50"
            >
              Clear Failed ({failedCount})
            </button>
          )}
        </div>
      </div>

      {/* Filters and Sort */}
      <div className="flex flex-wrap gap-4 mb-4">
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={statusOptions}
        />
        {profileOptions.length > 0 && (
          <FilterSelect
            label="Profile"
            value={profileFilter}
            onChange={setProfileFilter}
            options={profileOptions}
          />
        )}
        <SortSelect
          value={sortField}
          direction={sortDirection}
          onValueChange={handleSortFieldChange}
          onDirectionChange={handleSortDirectionChange}
          options={sortOptions}
        />
      </div>

      {filteredJobs.length > 0 ? (
        <div className="space-y-4">
          {filteredJobs.map((job) => (
            <HistoryJobCard
              key={job.id}
              job={job}
              onRetry={() => retryMutation.mutate(job.id)}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {jobs && jobs.length > 0 ? 'No jobs match the current filters' : 'No job history'}
          </p>
        </div>
      )}
    </div>
  )
}
