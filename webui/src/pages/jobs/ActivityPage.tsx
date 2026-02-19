import { useState, useMemo } from 'react'
import { useActiveJobs, useCancelJob } from '../../hooks/useJobs'
import type { JobInfo } from '../../api/types'
import { FilterSelect } from '../../components/ui/FilterSelect'
import { SortSelect } from '../../components/ui/SortSelect'

const SORT_FIELD_KEY = 'transcodr-activity-sort-field'
const SORT_DIR_KEY = 'transcodr-activity-sort-direction'

function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300'
    case 'pending':
      return 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-800 dark:text-yellow-300'
    case 'queued':
      return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
    default:
      return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60

  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

function JobCard({
  job,
  isExpanded,
  onToggle,
  onCancel,
}: {
  job: JobInfo
  isExpanded: boolean
  onToggle: () => void
  onCancel: () => void
}) {
  const filename = job.source_path.split('/').pop() || job.source_path

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header - clickable to expand */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        onClick={onToggle}
      >
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-2 min-w-0 flex-1">
            <ChevronIcon expanded={isExpanded} />
            <div className="min-w-0 flex-1">
              <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate" title={job.source_path}>
                {filename}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Profile: {job.profile}
                {job.total_profiles > 1 && ` (${job.profile_index + 1}/${job.total_profiles})`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(job.status)}`}>
              {job.status}
            </span>
            {(job.status === 'running' || job.status === 'pending' || job.status === 'queued') && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onCancel()
                }}
                className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        {/* Progress bar for running jobs */}
        {job.status === 'running' && (
          <div className="mt-3 ml-6">
            <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-1">
              <span>{job.progress.toFixed(1)}%</span>
              <div className="flex flex-wrap items-center justify-end gap-2 text-right">
                {(job.fps > 0 || job.frames_total > 0) && (
                  <span>
                    {job.fps > 0 && `${job.fps.toFixed(1)} fps`}
                    {job.frames_total > 0 && ` - ${job.frames_processed}/${job.frames_total} frames`}
                  </span>
                )}
                {job.eta_seconds !== null ? (
                  <span
                    className={
                      job.eta_quality === 'rough'
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-green-600 dark:text-green-400'
                    }
                  >
                    ETC {job.eta_quality === 'rough' ? '~' : ''}{formatDuration(job.eta_seconds)}
                  </span>
                ) : (
                  <span className="text-gray-500 dark:text-gray-500">Stabilizing...</span>
                )}
              </div>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className="bg-blue-600 dark:bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(job.progress, 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Expandable detail section */}
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-700 ml-6">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            {/* Left column - File info */}
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700 dark:text-gray-300">File Info</h4>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Source:</span>
                <p className="text-gray-900 dark:text-gray-100 text-xs break-all">{job.source_path}</p>
              </div>
              {job.output_path && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Output:</span>
                  <p className="text-gray-900 dark:text-gray-100 text-xs break-all">{job.output_path}</p>
                </div>
              )}
              <div className="flex gap-4">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Source size:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{formatBytes(job.source_size_bytes)}</span>
                </div>
                {job.output_size_bytes > 0 && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Output:</span>{' '}
                    <span className="text-gray-900 dark:text-gray-100">{formatBytes(job.output_size_bytes)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Right column - Encoding settings */}
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700 dark:text-gray-300">Encoding Settings</h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Video:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.video_codec || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Audio:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.audio_codec || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Container:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.container || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Subtitles:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.subtitle_mode || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">HW Accel:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.hardware_accel || 'none'}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Temp folder:</span>{' '}
                  <span className="text-gray-900 dark:text-gray-100">{job.use_temp_folder ? 'yes' : 'no'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Timestamps row */}
          <div className="mt-3 pt-2 border-t border-gray-100 dark:border-gray-700 flex gap-6 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Created:</span>{' '}
              <span className="text-gray-900 dark:text-gray-100">{formatDate(job.created_at)}</span>
            </div>
            {job.started_at && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Started:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100">{formatDate(job.started_at)}</span>
              </div>
            )}
            <div>
              <span className="text-gray-500 dark:text-gray-400">Job ID:</span>{' '}
              <span className="text-gray-900 dark:text-gray-100 font-mono text-xs">{job.id}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const statusOptions = [
  { value: 'running', label: 'Running' },
  { value: 'pending', label: 'Pending' },
  { value: 'queued', label: 'Queued' },
]

const sortOptions = [
  { value: 'created_at', label: 'Date Created' },
  { value: 'started_at', label: 'Date Started' },
  { value: 'filename', label: 'Filename' },
  { value: 'source_size_bytes', label: 'File Size' },
  { value: 'profile', label: 'Profile' },
]

export function ActivityPage() {
  const { data: jobs, isLoading, isError } = useActiveJobs()
  const cancelMutation = useCancelJob()
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [profileFilter, setProfileFilter] = useState('')
  const [sortField, setSortField] = useState(() => localStorage.getItem(SORT_FIELD_KEY) || 'created_at')
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
        case 'created_at':
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          break
        case 'started_at':
          const aStarted = a.started_at ? new Date(a.started_at).getTime() : 0
          const bStarted = b.started_at ? new Date(b.started_at).getTime() : 0
          comparison = aStarted - bStarted
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

  const handleCancel = (jobId: string) => {
    if (confirm('Are you sure you want to cancel this job?')) {
      cancelMutation.mutate(jobId)
    }
  }

  const toggleExpand = (jobId: string) => {
    setExpandedJobId((prev) => (prev === jobId ? null : jobId))
  }

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Jobs Activity</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Jobs Activity</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">Failed to load jobs</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Jobs Activity</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-4">Running and queued jobs. Click on a job to see details.</p>

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
            <JobCard
              key={job.id}
              job={job}
              isExpanded={expandedJobId === job.id}
              onToggle={() => toggleExpand(job.id)}
              onCancel={() => handleCancel(job.id)}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {jobs && jobs.length > 0 ? 'No jobs match the current filters' : 'No active jobs'}
          </p>
        </div>
      )}
    </div>
  )
}
