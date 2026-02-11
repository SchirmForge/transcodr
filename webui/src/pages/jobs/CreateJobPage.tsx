import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileBrowser } from '../../components/FileBrowser'
import { ProfileSelector } from '../../components/ProfileSelector'
import { useProfiles } from '../../hooks/useProfiles'
import { useSubmitJob } from '../../hooks/useCreateJob'
import type { EncodingRequest, OutputMode } from '../../api/types'

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{title}</h2>
      {children}
    </div>
  )
}

export function CreateJobPage() {
  // Source
  const [sourcePath, setSourcePath] = useState<string | null>(null)
  const [sourceType, setSourceType] = useState<'file' | 'directory' | null>(null)
  const [showSourceBrowser, setShowSourceBrowser] = useState(false)

  // Profiles
  const [selectedProfiles, setSelectedProfiles] = useState<string[]>([])
  const { data: allProfiles } = useProfiles()

  // Output
  const [outputMode, setOutputMode] = useState<OutputMode>('replace')
  const [useProfileDestination, setUseProfileDestination] = useState(false)
  const [destinationPath, setDestinationPath] = useState<string | null>(null)
  const [showDestBrowser, setShowDestBrowser] = useState(false)
  const [preserveStructure, setPreserveStructure] = useState(true)
  const [createProfileFolders, setCreateProfileFolders] = useState(false)
  const [backup, setBackup] = useState(true)
  const [backupDir, setBackupDir] = useState('.originals')

  // Processing options
  const [recursive, setRecursive] = useState(true)
  const [priority, setPriority] = useState(5)
  const [appendProfileName, setAppendProfileName] = useState(false)
  const [deleteSource, setDeleteSource] = useState(false)
  const [hardwareAccel, setHardwareAccel] = useState<string>('')
  const [useTempFolder, setUseTempFolder] = useState(true)
  const [copySourceToTemp, setCopySourceToTemp] = useState(true)

  // Submit
  const submitMutation = useSubmitJob()

  // Check if all selected profiles have destinations
  const allProfilesHaveDestination = selectedProfiles.length > 0 &&
    selectedProfiles.every((name) => {
      const profile = allProfiles?.find((p) => p.name === name)
      return profile?.destination
    })

  // Validation
  const canSubmit =
    sourcePath &&
    selectedProfiles.length > 0 &&
    (outputMode === 'replace' ||
      useProfileDestination ||
      destinationPath)

  const handleSubmit = () => {
    if (!sourcePath || selectedProfiles.length === 0) return

    const request: EncodingRequest = {
      source: sourcePath,
      profiles: selectedProfiles,
      output_mode: outputMode,
      recursive,
      priority,
      append_profile_name: appendProfileName,
      delete_source: deleteSource,
      use_temp_folder: useTempFolder,
      copy_source_to_temp: copySourceToTemp,
    }

    if (outputMode === 'replace') {
      request.backup = backup
      request.backup_dir = backupDir
    } else {
      request.use_profile_destination = useProfileDestination
      if (!useProfileDestination && destinationPath) {
        request.destination = destinationPath
      }
      request.preserve_structure = preserveStructure
      request.create_profile_folders = createProfileFolders
    }

    if (hardwareAccel) {
      request.hardware_accel = hardwareAccel
    }

    submitMutation.mutate(request)
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Create Job</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Submit a new encoding job.</p>

      <div className="space-y-6">
        {/* 1. Source Selection */}
        <SectionCard title="Source">
          {sourcePath ? (
            <div className="flex items-center gap-3">
              <span className={`px-2 py-1 text-xs font-medium rounded ${
                sourceType === 'directory'
                  ? 'bg-brand-100 dark:bg-brand-900/40 text-brand-800 dark:text-brand-200'
                  : 'bg-steel-100 dark:bg-graphite-800 text-graphite-800 dark:text-steel-200'
              }`}>
                {sourceType}
              </span>
              <span className="text-sm text-gray-900 dark:text-gray-100 truncate flex-1">{sourcePath}</span>
              <button
                onClick={() => { setSourcePath(null); setSourceType(null); setShowSourceBrowser(false) }}
                className="text-sm text-red-600 dark:text-red-400 hover:underline shrink-0"
              >
                Clear
              </button>
              <button
                onClick={() => setShowSourceBrowser(!showSourceBrowser)}
                className="text-sm text-brand-600 dark:text-brand-400 hover:underline shrink-0"
              >
                Change
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowSourceBrowser(!showSourceBrowser)}
              className="px-4 py-2 text-sm bg-brand-500 text-graphite-950 rounded hover:bg-brand-400 transition-colors"
            >
              {showSourceBrowser ? 'Hide Browser' : 'Select Source'}
            </button>
          )}

          {showSourceBrowser && (
            <div className="mt-4">
              <FileBrowser
                selectionMode="both"
                onSelect={(path, type) => {
                  setSourcePath(path)
                  setSourceType(type)
                  setShowSourceBrowser(false)
                }}
              />
            </div>
          )}
        </SectionCard>

        {/* 2. Profile Selection */}
        <SectionCard title="Profiles">
          {selectedProfiles.length > 0 && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              {selectedProfiles.length} profile{selectedProfiles.length > 1 ? 's' : ''} selected: {selectedProfiles.join(', ')}
            </p>
          )}
          <ProfileSelector
            selectedProfiles={selectedProfiles}
            onSelectionChange={setSelectedProfiles}
          />
        </SectionCard>

        {/* 3. Output Configuration */}
        <SectionCard title="Output Configuration">
          {/* Mode toggle */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => { setOutputMode('replace'); setUseProfileDestination(false) }}
              className={`px-4 py-2 text-sm rounded transition-colors ${
                outputMode === 'replace'
                  ? 'bg-brand-500 text-graphite-950'
                  : 'bg-steel-100 dark:bg-graphite-800 text-graphite-800 dark:text-steel-200 hover:bg-steel-200 dark:hover:bg-graphite-700'
              }`}
            >
              Replace
            </button>
            <button
              onClick={() => setOutputMode('destination')}
              className={`px-4 py-2 text-sm rounded transition-colors ${
                outputMode === 'destination'
                  ? 'bg-brand-500 text-graphite-950'
                  : 'bg-steel-100 dark:bg-graphite-800 text-graphite-800 dark:text-steel-200 hover:bg-steel-200 dark:hover:bg-graphite-700'
              }`}
            >
              Destination
            </button>
          </div>

          {outputMode === 'replace' ? (
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={backup}
                  onChange={(e) => setBackup(e.target.checked)}
                  className="rounded"
                />
                Backup original files
              </label>
              {backup && (
                <div>
                  <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Backup directory</label>
                  <input
                    type="text"
                    value={backupDir}
                    onChange={(e) => setBackupDir(e.target.value)}
                    className="w-full max-w-xs px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Use profile destinations */}
              <label className={`flex items-center gap-2 text-sm ${
                allProfilesHaveDestination
                  ? 'text-gray-700 dark:text-gray-300'
                  : 'text-gray-400 dark:text-gray-500'
              }`}>
                <input
                  type="checkbox"
                  checked={useProfileDestination}
                  onChange={(e) => setUseProfileDestination(e.target.checked)}
                  disabled={!allProfilesHaveDestination}
                  className="rounded"
                />
                Use profile destinations
                {!allProfilesHaveDestination && selectedProfiles.length > 0 && (
                  <span className="text-xs text-amber-600 dark:text-amber-400 ml-1">
                    (not all selected profiles have destinations)
                  </span>
                )}
              </label>

              {/* Destination folder browser */}
              {!useProfileDestination && (
                <div>
                  <label className="block text-sm text-gray-600 dark:text-gray-400 mb-2">Destination folder</label>
                  {destinationPath ? (
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-sm text-gray-900 dark:text-gray-100 truncate flex-1">{destinationPath}</span>
                      <button
                        onClick={() => { setDestinationPath(null); setShowDestBrowser(false) }}
                        className="text-sm text-red-600 dark:text-red-400 hover:underline shrink-0"
                      >
                        Clear
                      </button>
                      <button
                        onClick={() => setShowDestBrowser(!showDestBrowser)}
                        className="text-sm text-brand-600 dark:text-brand-400 hover:underline shrink-0"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowDestBrowser(!showDestBrowser)}
                      className="px-4 py-2 text-sm bg-steel-100 dark:bg-graphite-800 text-graphite-800 dark:text-steel-200 rounded hover:bg-steel-200 dark:hover:bg-graphite-700 transition-colors"
                    >
                      {showDestBrowser ? 'Hide Browser' : 'Select Destination'}
                    </button>
                  )}
                  {showDestBrowser && (
                    <div className="mt-2">
                      <FileBrowser
                        selectionMode="directory"
                        onSelect={(path) => {
                          setDestinationPath(path)
                          setShowDestBrowser(false)
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Additional options */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={preserveStructure}
                    onChange={(e) => setPreserveStructure(e.target.checked)}
                    className="rounded"
                  />
                  Preserve folder structure
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={createProfileFolders}
                    onChange={(e) => setCreateProfileFolders(e.target.checked)}
                    disabled={useProfileDestination}
                    className="rounded"
                  />
                  Create subfolder per profile
                </label>
              </div>
            </div>
          )}
        </SectionCard>

        {/* 4. Processing Options */}
        <SectionCard title="Processing Options">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.target.checked)}
                  className="rounded"
                />
                Process subdirectories recursively
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={appendProfileName}
                  onChange={(e) => setAppendProfileName(e.target.checked)}
                  className="rounded"
                />
                Append profile name to filename
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={deleteSource}
                  onChange={(e) => setDeleteSource(e.target.checked)}
                  className="rounded"
                />
                Delete source after encoding
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={useTempFolder}
                  onChange={(e) => setUseTempFolder(e.target.checked)}
                  className="rounded"
                />
                Encode to temp folder first
                <span className="text-xs text-gray-400 dark:text-gray-500">(safer, requires temp disk space)</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={copySourceToTemp}
                  onChange={(e) => setCopySourceToTemp(e.target.checked)}
                  className="rounded"
                />
                Copy source to temp before encoding
                <span className="text-xs text-gray-400 dark:text-gray-500">(recommended for network storage)</span>
              </label>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                  Priority: {priority}
                </label>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                  className="w-full max-w-xs"
                />
                <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500 max-w-xs">
                  <span>Low</span>
                  <span>High</span>
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Hardware acceleration</label>
                <select
                  value={hardwareAccel}
                  onChange={(e) => setHardwareAccel(e.target.value)}
                  className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Auto (from config)</option>
                  <option value="vaapi">VAAPI</option>
                  <option value="nvenc">NVENC</option>
                  <option value="qsv">QSV</option>
                  <option value="none">None (CPU)</option>
                </select>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* 5. Review & Submit */}
        <SectionCard title="Review & Submit">
          {/* Summary */}
          <div className="text-sm space-y-1 mb-4">
            <div className="flex gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24">Source:</span>
              <span className="text-gray-900 dark:text-gray-100">{sourcePath || <span className="text-amber-600 dark:text-amber-400">Not selected</span>}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24">Profiles:</span>
              <span className="text-gray-900 dark:text-gray-100">
                {selectedProfiles.length > 0
                  ? selectedProfiles.join(', ')
                  : <span className="text-amber-600 dark:text-amber-400">None selected</span>
                }
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-500 dark:text-gray-400 w-24">Output:</span>
              <span className="text-gray-900 dark:text-gray-100">
                {outputMode === 'replace'
                  ? `Replace in-place${backup ? ' (with backup)' : ''}`
                  : useProfileDestination
                    ? 'Profile destinations'
                    : destinationPath || <span className="text-amber-600 dark:text-amber-400">No destination</span>
                }
              </span>
            </div>
          </div>

          {/* Submit */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || submitMutation.isPending}
              className="px-6 py-2 text-sm bg-brand-500 text-graphite-950 rounded hover:bg-brand-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitMutation.isPending ? 'Submitting...' : 'Submit Job'}
            </button>

            {submitMutation.isError && (
              <p className="text-sm text-red-600 dark:text-red-400">
                {(submitMutation.error as Error)?.message || 'Failed to submit job'}
              </p>
            )}
          </div>

          {/* Success */}
          {submitMutation.isSuccess && submitMutation.data && (
            <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
              <p className="text-sm text-green-800 dark:text-green-300 font-medium">
                {submitMutation.data.message}
              </p>
              <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                Job IDs: {submitMutation.data.job_ids.join(', ')}
              </p>
              <Link
                to="/jobs/activity"
                className="text-sm text-brand-600 dark:text-brand-400 hover:underline mt-2 inline-block"
              >
                View in Activity
              </Link>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
