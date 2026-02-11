import { useProfiles } from '../hooks/useProfiles'
import type { ProfileInfo } from '../api/types'

interface ProfileSelectorProps {
  selectedProfiles: string[]
  onSelectionChange: (profiles: string[]) => void
}

function ProfileCard({
  profile,
  isSelected,
  onToggle,
}: {
  profile: ProfileInfo
  isSelected: boolean
  onToggle: () => void
}) {
  const hasDestination = !!profile.destination

  return (
    <div
      onClick={onToggle}
      className={`p-4 bg-white dark:bg-gray-800 rounded-lg shadow cursor-pointer transition-all ${
        isSelected
          ? 'ring-2 ring-brand-500 dark:ring-brand-400'
          : 'hover:shadow-md'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-medium text-gray-900 dark:text-gray-100">{profile.name}</h3>
        <div className="flex items-center gap-2">
          {/* Destination indicator */}
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              hasDestination
                ? 'bg-green-500'
                : 'bg-amber-400'
            }`}
            title={hasDestination ? `Destination: ${profile.destination}` : 'No destination set'}
          />
          <span
            className={`px-2 py-1 text-xs font-medium rounded ${
              profile.source === 'builtin'
                ? 'bg-brand-100 dark:bg-brand-900/40 text-brand-800 dark:text-brand-200'
                : 'bg-steel-100 dark:bg-graphite-800 text-graphite-800 dark:text-steel-200'
            }`}
          >
            {profile.source}
          </span>
        </div>
      </div>

      <dl className="text-sm space-y-1">
        {profile.codec && (
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Codec</dt>
            <dd className="text-gray-900 dark:text-gray-100">{profile.codec}</dd>
          </div>
        )}
        {profile.container && (
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Container</dt>
            <dd className="text-gray-900 dark:text-gray-100">{profile.container}</dd>
          </div>
        )}
        {profile.crf !== undefined && (
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">CRF</dt>
            <dd className="text-gray-900 dark:text-gray-100">{profile.crf}</dd>
          </div>
        )}
      </dl>
    </div>
  )
}

export function ProfileSelector({ selectedProfiles, onSelectionChange }: ProfileSelectorProps) {
  const { data: profiles, isLoading, isError } = useProfiles()

  const toggleProfile = (name: string) => {
    if (selectedProfiles.includes(name)) {
      onSelectionChange(selectedProfiles.filter((p) => p !== name))
    } else {
      onSelectionChange([...selectedProfiles, name])
    }
  }

  if (isLoading) {
    return <div className="text-sm text-gray-500 dark:text-gray-400">Loading profiles...</div>
  }

  if (isError) {
    return <div className="text-sm text-red-600 dark:text-red-400">Failed to load profiles</div>
  }

  if (!profiles || profiles.length === 0) {
    return <div className="text-sm text-gray-500 dark:text-gray-400">No profiles available</div>
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
          <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
          Has destination
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          No destination
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {profiles.map((profile) => (
          <ProfileCard
            key={profile.name}
            profile={profile}
            isSelected={selectedProfiles.includes(profile.name)}
            onToggle={() => toggleProfile(profile.name)}
          />
        ))}
      </div>
    </div>
  )
}
