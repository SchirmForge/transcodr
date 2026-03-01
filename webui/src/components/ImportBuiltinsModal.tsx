import { useEffect, useState } from 'react'
import { useBuiltinProfiles, useImportBuiltins } from '../hooks/useProfiles'
import type { BuiltinProfileEntry, ImportBuiltinsResponse } from '../api/types'

interface Props {
  onClose: () => void
}

export function ImportBuiltinsModal({ onClose }: Props) {
  const { data: builtins, isLoading, isError } = useBuiltinProfiles()
  const importMutation = useImportBuiltins()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<ImportBuiltinsResponse | null>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  function toggleProfile(name: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  async function handleImport() {
    if (selected.size === 0) return
    try {
      const res = await importMutation.mutateAsync({ names: [...selected] })
      setResult(res)
      setSelected(new Set())
    } catch {
      // error shown via importMutation.isError
    }
  }

  const installableCount = builtins?.filter(b => !b.already_installed).length ?? 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-lg flex flex-col max-h-[80vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
            Import built-in profiles
          </span>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none"
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="overflow-auto flex-1 p-4">
          {isLoading && (
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
          )}
          {isError && (
            <p className="text-sm text-red-600 dark:text-red-400">
              Failed to load built-in profiles.
            </p>
          )}
          {importMutation.isError && (
            <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800">
              <p className="text-xs text-red-600 dark:text-red-400">
                Import failed. Check the daemon logs.
              </p>
            </div>
          )}
          {result && (
            <div className="mb-3 p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800">
              <p className="text-xs text-green-700 dark:text-green-400">
                {result.imported.length > 0
                  ? `Imported: ${result.imported.join(', ')}`
                  : 'No new profiles imported (all already present).'}
              </p>
            </div>
          )}
          {builtins && (
            <ul className="space-y-2">
              {builtins.map((profile: BuiltinProfileEntry) => (
                <li key={profile.name}>
                  <label
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                      profile.already_installed
                        ? 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 opacity-60 cursor-default'
                        : selected.has(profile.name)
                        ? 'border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 cursor-pointer'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 cursor-pointer'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={profile.already_installed || selected.has(profile.name)}
                      disabled={profile.already_installed}
                      onChange={() => toggleProfile(profile.name)}
                      className="mt-0.5 shrink-0"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {profile.name}
                        </span>
                        {profile.already_installed && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                            installed
                          </span>
                        )}
                        {profile.tags?.map(tag => (
                          <span
                            key={tag}
                            className="text-xs px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      {profile.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {profile.description}
                        </p>
                      )}
                    </div>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {builtins && installableCount === 0 && !result && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center mt-2">
              All built-in profiles are already installed.
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 shrink-0 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Close
          </button>
          <button
            onClick={handleImport}
            disabled={selected.size === 0 || importMutation.isPending}
            className="px-3 py-1.5 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importMutation.isPending
              ? 'Importing…'
              : selected.size > 0
              ? `Import (${selected.size})`
              : 'Import'}
          </button>
        </div>
      </div>
    </div>
  )
}
