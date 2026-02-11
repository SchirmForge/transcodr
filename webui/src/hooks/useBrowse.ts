import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { BrowseResponse } from '../api/types'

export function useBrowse(path: string | null) {
  return useQuery({
    queryKey: ['browse', path],
    queryFn: async (): Promise<BrowseResponse> => {
      const params = path ? { path } : {}
      const { data } = await apiClient.get<BrowseResponse>('/browse', { params })
      return data
    },
    staleTime: 30000,
    refetchInterval: false,
  })
}
