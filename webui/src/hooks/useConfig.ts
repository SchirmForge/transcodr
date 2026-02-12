import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { TranscodrConfig, ConfigUpdateResponse, ReloadResponse } from '../api/types'

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: async (): Promise<TranscodrConfig> => {
      const { data } = await apiClient.get<TranscodrConfig>('/config')
      return data
    },
    staleTime: 60000,
    refetchInterval: false,
  })
}

export function useUpdateConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (update: Partial<TranscodrConfig>): Promise<ConfigUpdateResponse> => {
      const { data } = await apiClient.put<ConfigUpdateResponse>('/config', update)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

export function useReloadConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<ReloadResponse> => {
      const { data } = await apiClient.post<ReloadResponse>('/reload')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      queryClient.invalidateQueries({ queryKey: ['watchfolders'] })
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
    },
  })
}
