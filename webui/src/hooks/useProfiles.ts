import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { ProfilesResponse, ProfileInfo } from '../api/types'

// Fetch all profiles
export function useProfiles() {
  return useQuery({
    queryKey: ['profiles'],
    queryFn: async (): Promise<ProfileInfo[]> => {
      const { data } = await apiClient.get<ProfilesResponse>('/profiles')
      return data.profiles
    },
  })
}

// Fetch single profile
export function useProfile(name: string | undefined) {
  return useQuery({
    queryKey: ['profile', name],
    queryFn: async (): Promise<ProfileInfo> => {
      const { data } = await apiClient.get<ProfileInfo>(`/profiles/${name}`)
      return data
    },
    enabled: !!name,
  })
}
