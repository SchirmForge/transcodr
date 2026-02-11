import { useState, useEffect } from 'react'
import { useBrowse } from '../hooks/useBrowse'
import type { BrowseEntry } from '../api/types'

interface FileBrowserProps {
  onSelect: (path: string, type: 'file' | 'directory') => void
  selectionMode: 'file' | 'directory' | 'both'
  initialPath?: string | null
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function FolderIcon() {
  return (
    <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
      <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg className="w-5 h-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
    </svg>
  )
}

function Breadcrumbs({ path, onNavigate }: { path: string; onNavigate: (path: string) => void }) {
  const parts = path.split('/').filter(Boolean)

  return (
    <div className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto">
      <button
        onClick={() => onNavigate('/')}
        className="hover:text-blue-600 dark:hover:text-blue-400 shrink-0"
      >
        /
      </button>
      {parts.map((part, i) => {
        const fullPath = '/' + parts.slice(0, i + 1).join('/')
        return (
          <span key={fullPath} className="flex items-center gap-1 shrink-0">
            <span className="text-gray-400">/</span>
            <button
              onClick={() => onNavigate(fullPath)}
              className="hover:text-blue-600 dark:hover:text-blue-400"
            >
              {part}
            </button>
          </span>
        )
      })}
    </div>
  )
}

export function FileBrowser({ onSelect, selectionMode, initialPath }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState<string | null>(initialPath ?? null)
  const { data, isLoading, isError, error, refetch, isFetching } = useBrowse(currentPath)

  // Update path when browse response comes back (handles initial null -> root_media)
  useEffect(() => {
    if (data && currentPath === null) {
      setCurrentPath(data.current_path)
    }
  }, [data, currentPath])

  const handleEntryClick = (entry: BrowseEntry) => {
    if (entry.type === 'directory') {
      setCurrentPath(entry.path)
    } else if (entry.type === 'file' && (selectionMode === 'file' || selectionMode === 'both')) {
      onSelect(entry.path, 'file')
    }
  }

  const handleSelectDirectory = (e: React.MouseEvent, entry: BrowseEntry) => {
    e.stopPropagation()
    onSelect(entry.path, 'directory')
  }

  const navigateToHome = () => {
    if (data?.root_media) {
      setCurrentPath(data.root_media)
    }
  }

  const navigateUp = () => {
    if (data?.parent_path) {
      setCurrentPath(data.parent_path)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-3 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={navigateToHome}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
          title="Home (root_media)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </button>
        <button
          onClick={navigateUp}
          disabled={!data?.parent_path}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 disabled:opacity-30"
          title="Go up"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 disabled:opacity-30"
          title="Refresh"
        >
          <svg className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          {data && <Breadcrumbs path={data.current_path} onNavigate={setCurrentPath} />}
        </div>
      </div>

      {/* Content */}
      <div className="max-h-80 overflow-y-auto">
        {isLoading && (
          <div className="p-4 text-sm text-gray-500 dark:text-gray-400">Loading...</div>
        )}

        {isError && (
          <div className="p-4 text-sm text-red-600 dark:text-red-400">
            {(error as Error)?.message || 'Failed to load directory'}
          </div>
        )}

        {data && data.entries.length === 0 && (
          <div className="p-4 text-sm text-gray-500 dark:text-gray-400">
            No video files or subdirectories found
          </div>
        )}

        {data && data.entries.map((entry) => (
          <div
            key={entry.path}
            onClick={() => handleEntryClick(entry)}
            className={`flex items-center gap-3 px-4 py-2 border-b border-gray-100 dark:border-gray-700 last:border-b-0 transition-colors ${
              entry.type === 'file' && (selectionMode === 'file' || selectionMode === 'both')
                ? 'cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/20'
                : entry.type === 'directory'
                  ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700'
                  : ''
            }`}
          >
            {entry.type === 'directory' ? <FolderIcon /> : <FileIcon />}
            <span className="flex-1 text-sm text-gray-900 dark:text-gray-100 truncate">
              {entry.name}
            </span>
            {entry.type === 'file' && entry.size != null && (
              <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
                {formatBytes(entry.size)}
              </span>
            )}
            {entry.type === 'directory' && (selectionMode === 'directory' || selectionMode === 'both') && (
              <button
                onClick={(e) => handleSelectDirectory(e, entry)}
                className="px-2 py-1 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded transition-colors shrink-0"
              >
                Select
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Select current directory button */}
      {(selectionMode === 'directory' || selectionMode === 'both') && data && (
        <div className="p-3 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => onSelect(data.current_path, 'directory')}
            className="w-full px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Select This Folder
          </button>
        </div>
      )}
    </div>
  )
}
