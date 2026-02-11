import { useProfiles } from '../../hooks/useProfiles'
import type { ProfileInfo } from '../../api/types'

function ProfileCard({ profile }: { profile: ProfileInfo }) {
  return (
    <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-medium text-gray-900 dark:text-gray-100">{profile.name}</h3>
        <span
          className={`px-2 py-1 text-xs font-medium rounded ${
            profile.source === 'builtin'
              ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300'
              : 'bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300'
          }`}
        >
          {profile.source}
        </span>
      </div>

      {profile.description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{profile.description}</p>
      )}

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
        {profile.preset && (
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Preset</dt>
            <dd className="text-gray-900 dark:text-gray-100">{profile.preset}</dd>
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

export function ProfilesPage() {
  const { data: profiles, isLoading, isError } = useProfiles()

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Profiles</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Profiles</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">Failed to load profiles</p>
        </div>
      </div>
    )
  }

  const builtinProfiles = profiles?.filter(p => p.source === 'builtin') || []
  const userProfiles = profiles?.filter(p => p.source === 'user') || []

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Profiles</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-4">Encoding profiles available for jobs.</p>

      {profiles && profiles.length > 0 ? (
        <div className="space-y-6">
          {userProfiles.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">User Profiles</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {userProfiles.map((profile) => (
                  <ProfileCard key={profile.name} profile={profile} />
                ))}
              </div>
            </div>
          )}

          {builtinProfiles.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Built-in Profiles</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {builtinProfiles.map((profile) => (
                  <ProfileCard key={profile.name} profile={profile} />
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">No profiles loaded</p>
        </div>
      )}
    </div>
  )
}
