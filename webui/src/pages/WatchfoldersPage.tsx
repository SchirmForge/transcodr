import { useWatchfolders, usePauseWatchfolder, useResumeWatchfolder } from '../hooks/useWatchfolders'
import type { WatchFolderInfo } from '../api/types'

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
  const folderName = folder.path.split('/').pop() || folder.path
  const isMediaWatcher = folder.type === 'media'

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between items-start mb-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-medium text-gray-900 truncate" title={folder.path}>
            {folderName}
          </h3>
          <p className="text-sm text-gray-500 truncate" title={folder.path}>
            {folder.path}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <span
            className={`px-2 py-1 text-xs font-medium rounded ${
              folder.paused
                ? 'bg-yellow-100 text-yellow-800'
                : folder.active
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
            }`}
          >
            {folder.paused ? 'Paused' : folder.active ? 'Active' : 'Inactive'}
          </span>
          {folder.paused ? (
            <button
              onClick={onResume}
              disabled={isResuming}
              className="px-2 py-1 text-xs bg-green-100 hover:bg-green-200 text-green-700 rounded transition-colors disabled:opacity-50"
            >
              Resume
            </button>
          ) : folder.active ? (
            <button
              onClick={onPause}
              disabled={isPausing}
              className="px-2 py-1 text-xs bg-yellow-100 hover:bg-yellow-200 text-yellow-700 rounded transition-colors disabled:opacity-50"
            >
              Pause
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div>
          <span className="text-gray-500">Type:</span>{' '}
          <span className="text-gray-900 capitalize">{folder.type}</span>
        </div>
        <div>
          <span className="text-gray-500">Scan:</span>{' '}
          <span className="text-gray-900">{folder.scan_interval}s</span>
        </div>

        {isMediaWatcher && folder.profiles && (
          <div>
            <span className="text-gray-500">Profiles:</span>{' '}
            <span className="text-gray-900">{folder.profiles.join(', ')}</span>
          </div>
        )}

        {isMediaWatcher && folder.file_patterns && (
          <div>
            <span className="text-gray-500">Patterns:</span>{' '}
            <span className="text-gray-900 text-xs">{folder.file_patterns.join(', ')}</span>
          </div>
        )}

        {isMediaWatcher && (
          <div>
            <span className="text-gray-500">Output:</span>{' '}
            <span className="text-gray-900">
              {folder.use_profile_destination
                ? 'Profile destinations'
                : folder.destination
                  ? folder.destination.split('/').pop()
                  : '-'}
            </span>
          </div>
        )}

        {isMediaWatcher && (folder.pending_files !== undefined && folder.pending_files > 0) && (
          <div>
            <span className="text-gray-500">Pending:</span>{' '}
            <span className="text-gray-900">{folder.pending_files} files</span>
          </div>
        )}

        {isMediaWatcher && (folder.submitted_jobs !== undefined && folder.submitted_jobs > 0) && (
          <div>
            <span className="text-gray-500">Submitted:</span>{' '}
            <span className="text-gray-900">{folder.submitted_jobs} jobs</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function WatchfoldersPage() {
  const { data: watchfolders, isLoading, isError } = useWatchfolders()
  const pauseMutation = usePauseWatchfolder()
  const resumeMutation = useResumeWatchfolder()

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Watch Folders</h1>
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Watch Folders</h1>
        <div className="mt-6 p-4 bg-red-50 rounded-lg shadow border border-red-200">
          <p className="text-red-600 text-sm">Failed to load watch folders</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Watch Folders</h1>
      <p className="text-gray-600 mb-4">Configured watch folders and their status.</p>

      {watchfolders && watchfolders.length > 0 ? (
        <div className="space-y-4">
          {watchfolders.map((folder) => (
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
        <div className="p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">No watch folders configured</p>
        </div>
      )}
    </div>
  )
}
