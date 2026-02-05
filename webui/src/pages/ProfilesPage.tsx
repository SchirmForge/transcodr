import { useProfiles } from '../hooks/useProfiles'
import type { ProfileInfo } from '../api/types'

function ProfileCard({ profile }: { profile: ProfileInfo }) {
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-medium text-gray-900">{profile.name}</h3>
        <span
          className={`px-2 py-1 text-xs font-medium rounded ${
            profile.source === 'builtin'
              ? 'bg-blue-100 text-blue-800'
              : 'bg-purple-100 text-purple-800'
          }`}
        >
          {profile.source}
        </span>
      </div>

      {profile.description && (
        <p className="text-sm text-gray-600 mb-3">{profile.description}</p>
      )}

      <dl className="text-sm space-y-1">
        {profile.codec && (
          <div className="flex justify-between">
            <dt className="text-gray-500">Codec</dt>
            <dd className="text-gray-900">{profile.codec}</dd>
          </div>
        )}
        {profile.container && (
          <div className="flex justify-between">
            <dt className="text-gray-500">Container</dt>
            <dd className="text-gray-900">{profile.container}</dd>
          </div>
        )}
        {profile.preset && (
          <div className="flex justify-between">
            <dt className="text-gray-500">Preset</dt>
            <dd className="text-gray-900">{profile.preset}</dd>
          </div>
        )}
        {profile.crf !== undefined && (
          <div className="flex justify-between">
            <dt className="text-gray-500">CRF</dt>
            <dd className="text-gray-900">{profile.crf}</dd>
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
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Profiles</h1>
        <div className="mt-6 p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Profiles</h1>
        <div className="mt-6 p-4 bg-red-50 rounded-lg shadow border border-red-200">
          <p className="text-red-600 text-sm">Failed to load profiles</p>
        </div>
      </div>
    )
  }

  const builtinProfiles = profiles?.filter(p => p.source === 'builtin') || []
  const userProfiles = profiles?.filter(p => p.source === 'user') || []

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Profiles</h1>
      <p className="text-gray-600 mb-4">Encoding profiles available for jobs.</p>

      {profiles && profiles.length > 0 ? (
        <div className="space-y-6">
          {userProfiles.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-800 mb-3">User Profiles</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {userProfiles.map((profile) => (
                  <ProfileCard key={profile.name} profile={profile} />
                ))}
              </div>
            </div>
          )}

          {builtinProfiles.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-800 mb-3">Built-in Profiles</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {builtinProfiles.map((profile) => (
                  <ProfileCard key={profile.name} profile={profile} />
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 bg-white rounded-lg shadow">
          <p className="text-gray-500 text-sm">No profiles loaded</p>
        </div>
      )}
    </div>
  )
}
