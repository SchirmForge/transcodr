import { useState } from 'react'
import { useActiveJobs, useCancelJob } from '../../hooks/useJobs'
import type { JobInfo } from '../../api/types'

function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return 'bg-blue-100 text-blue-800'
    case 'pending':
      return 'bg-yellow-100 text-yellow-800'
    case 'queued':
      return 'bg-gray-100 text-gray-800'
    default:
      return 'bg-gray-100 text-gray-800'
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

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
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
    <div className="bg-white rounded-lg shadow">
      {/* Header - clickable to expand */}
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-2 min-w-0 flex-1">
            <ChevronIcon expanded={isExpanded} />
            <div className="min-w-0 flex-1">
              <h3 className="font-medium text-gray-900 truncate" title={job.source_path}>
                {filename}
              </h3>
              <p className="text-sm text-gray-500">
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
                className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        {/* Progress bar for running jobs */}
        {job.status === 'running' && (
          <div className="mt-3 ml-6">
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>{job.progress.toFixed(1)}%</span>
              <span>
                {job.fps > 0 && `${job.fps.toFixed(1)} fps`}
                {job.frames_total > 0 && ` • ${job.frames_processed}/${job.frames_total} frames`}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
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
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 ml-6">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            {/* Left column - File info */}
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700">File Info</h4>
              <div>
                <span className="text-gray-500">Source:</span>
                <p className="text-gray-900 text-xs break-all">{job.source_path}</p>
              </div>
              {job.output_path && (
                <div>
                  <span className="text-gray-500">Output:</span>
                  <p className="text-gray-900 text-xs break-all">{job.output_path}</p>
                </div>
              )}
              <div className="flex gap-4">
                <div>
                  <span className="text-gray-500">Source size:</span>{' '}
                  <span className="text-gray-900">{formatBytes(job.source_size_bytes)}</span>
                </div>
                {job.output_size_bytes > 0 && (
                  <div>
                    <span className="text-gray-500">Output:</span>{' '}
                    <span className="text-gray-900">{formatBytes(job.output_size_bytes)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Right column - Encoding settings */}
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700">Encoding Settings</h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <div>
                  <span className="text-gray-500">Video:</span>{' '}
                  <span className="text-gray-900">{job.video_codec || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Audio:</span>{' '}
                  <span className="text-gray-900">{job.audio_codec || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Container:</span>{' '}
                  <span className="text-gray-900">{job.container || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Subtitles:</span>{' '}
                  <span className="text-gray-900">{job.subtitle_mode || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">HW Accel:</span>{' '}
                  <span className="text-gray-900">{job.hardware_accel || 'none'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Temp folder:</span>{' '}
                  <span className="text-gray-900">{job.use_temp_folder ? 'yes' : 'no'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Timestamps row */}
          <div className="mt-3 pt-2 border-t border-gray-100 flex gap-6 text-sm">
            <div>
              <span className="text-gray-500">Created:</span>{' '}
              <span className="text-gray-900">{formatDate(job.created_at)}</span>
            </div>
            {job.started_at && (
              <div>
                <span className="text-gray-500">Started:</span>{' '}
                <span className="text-gray-900">{formatDate(job.started_at)}</span>
              </div>
            )}
            <div>
              <span className="text-gray-500">Job ID:</span>{' '}
              <span className="text-gray-900 font-mono text-xs">{job.id}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function ActivityPage() {
  const { data: jobs, isLoading, isError } = useActiveJobs()
  const cancelMutation = useCancelJob()
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)

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
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs Activity</h1>
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs Activity</h1>
        <div className="mt-6 p-4 bg-red-50 rounded-lg shadow border border-red-200">
          <p className="text-red-600 text-sm">Failed to load jobs</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs Activity</h1>
      <p className="text-gray-600 mb-4">Running and queued jobs. Click on a job to see details.</p>

      {jobs && jobs.length > 0 ? (
        <div className="space-y-4">
          {jobs.map((job) => (
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
        <div className="p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">No active jobs</p>
        </div>
      )}
    </div>
  )
}
