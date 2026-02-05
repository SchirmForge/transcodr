import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { DaemonStatus } from '../api/types'

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: async (): Promise<DaemonStatus> => {
      const { data } = await apiClient.get<DaemonStatus>('/status')
      return data
    },
  })
}
