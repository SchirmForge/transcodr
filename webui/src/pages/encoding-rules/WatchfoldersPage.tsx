import { useState, useMemo } from 'react'
import { useWatchfolders, usePauseWatchfolder, useResumeWatchfolder } from '../../hooks/useWatchfolders'
import type { WatchFolderInfo } from '../../api/types'
import { FilterSelect } from '../../components/ui/FilterSelect'

function WatchfolderCard({
  folder,
  onPause,
  onResume,
  isPausing,
  isResuming,
}: {
  folder: WatchFolderInfo
  onPause: () => void
  onResume: () => void
  isPausing: boolean
  isResuming: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const folderName = folder.path.split('/').pop() || folder.path
  const isInvalid = !!(folder.errors?.length)
  const isMediaWatcher = folder.type === 'media'

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header — always visible */}
      <div className="flex items-center gap-2 p-4">
        <button
          onClick={() => setExpanded(e => !e)}
          className="shrink-0 w-5 text-center text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 font-mono text-sm leading-none"
          title={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? '−' : '+'}
        </button>

        <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate flex-1 min-w-0" title={folder.path}>
          {folderName}
        </h3>

        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`px-2 py-1 text-xs font-medium rounded ${
              isInvalid
                ? 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300'
                : folder.paused
                  ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-800 dark:text-yellow-300'
                  : folder.active
                    ? 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
            }`}
          >
            {isInvalid ? 'Invalid' : folder.paused ? 'Paused' : folder.active ? 'Active' : 'Inactive'}
          </span>

          {!isInvalid && folder.paused ? (
            <button
              onClick={onResume}
              disabled={isResuming}
              className="px-2 py-1 text-xs bg-green-100 dark:bg-green-900/50 hover:bg-green-200 dark:hover:bg-green-900/70 text-green-700 dark:text-green-300 rounded transition-colors disabled:opacity-50"
            >
              Resume
            </button>
          ) : !isInvalid && folder.active ? (
            <button
              onClick={onPause}
              disabled={isPausing}
              className="px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-900/50 hover:bg-yellow-200 dark:hover:bg-yellow-900/70 text-yellow-700 dark:text-yellow-300 rounded transition-colors disabled:opacity-50"
            >
              Pause
            </button>
          ) : null}
        </div>
      </div>

      {/* Details — only when expanded */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700 pt-3">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 break-all">{folder.path}</p>

          {folder.errors && folder.errors.length > 0 && (
            <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
              {folder.errors.map((err, i) => (
                <p key={i} className="text-xs text-red-600 dark:text-red-400">{err}</p>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Type:</span>{' '}
              <span className="text-gray-900 dark:text-gray-100 capitalize">{folder.type}</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Scan:</span>{' '}
              <span className="text-gray-900 dark:text-gray-100">{folder.scan_interval}s</span>
            </div>

            {isMediaWatcher && folder.profiles && (
              <div className="col-span-2">
                <span className="text-gray-500 dark:text-gray-400">Profiles:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100">{folder.profiles.join(', ')}</span>
              </div>
            )}

            {isMediaWatcher && folder.file_patterns && (
              <div className="col-span-2">
                <span className="text-gray-500 dark:text-gray-400">Patterns:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100 text-xs">{folder.file_patterns.join(', ')}</span>
              </div>
            )}

            {isMediaWatcher && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Output:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100">
                  {folder.use_profile_destination
                    ? 'Profile destinations'
                    : folder.destination
                      ? folder.destination
                      : '-'}
                </span>
              </div>
            )}

            {isMediaWatcher && (folder.pending_files !== undefined && folder.pending_files > 0) && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Pending:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100">{folder.pending_files} files</span>
              </div>
            )}

            {isMediaWatcher && (folder.submitted_jobs !== undefined && folder.submitted_jobs > 0) && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">Submitted:</span>{' '}
                <span className="text-gray-900 dark:text-gray-100">{folder.submitted_jobs} jobs</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const typeOptions = [
  { value: 'command', label: 'Command' },
  { value: 'media', label: 'Media' },
]

const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'invalid', label: 'Invalid' },
]

function getWatchfolderStatus(folder: WatchFolderInfo): string {
  if (folder.errors?.length) return 'invalid'
  if (folder.paused) return 'paused'
  if (folder.active) return 'active'
  return 'inactive'
}

export function WatchfoldersPage() {
  const { data: watchfolders, isLoading, isError, isFetching, refetch } = useWatchfolders()
  const pauseMutation = usePauseWatchfolder()
  const resumeMutation = useResumeWatchfolder()
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Filter watchfolders
  const filteredWatchfolders = useMemo(() => {
    if (!watchfolders) return []
    let result = [...watchfolders]

    if (typeFilter) {
      result = result.filter(f => f.type === typeFilter)
    }
    if (statusFilter) {
      result = result.filter(f => getWatchfolderStatus(f) === statusFilter)
    }

    return result
  }, [watchfolders, typeFilter, statusFilter])

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Watch Folders</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Watch Folders</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">Failed to load watch folders</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Watch Folders</h1>
          <p className="text-gray-600 dark:text-gray-400">Configured watch folders and their status.</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isFetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4">
        <FilterSelect
          label="Type"
          value={typeFilter}
          onChange={setTypeFilter}
          options={typeOptions}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={statusOptions}
        />
      </div>

      {filteredWatchfolders.length > 0 ? (
        <div className="space-y-4">
          {filteredWatchfolders.map((folder) => (
            <WatchfolderCard
              key={folder.id}
              folder={folder}
              onPause={() => pauseMutation.mutate(folder.id)}
              onResume={() => resumeMutation.mutate(folder.id)}
              isPausing={pauseMutation.isPending}
              isResuming={resumeMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {watchfolders && watchfolders.length > 0 ? 'No watch folders match the current filters' : 'No watch folders configured'}
          </p>
        </div>
      )}
    </div>
  )
}
