import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { WatchfoldersResponse, WatchFolderInfo, ActionResponse } from '../api/types'

// Fetch all watchfolders
export function useWatchfolders() {
  return useQuery({
    queryKey: ['watchfolders'],
    queryFn: async (): Promise<WatchFolderInfo[]> => {
      const { data } = await apiClient.get<WatchfoldersResponse>('/watchfolders')
      return data.watchfolders
    },
  })
}

// Fetch single watchfolder
export function useWatchfolder(folderId: string | undefined) {
  return useQuery({
    queryKey: ['watchfolder', folderId],
    queryFn: async (): Promise<WatchFolderInfo> => {
      const { data } = await apiClient.get<WatchFolderInfo>(`/watchfolders/${folderId}`)
      return data
    },
    enabled: !!folderId,
  })
}

// Pause watchfolder mutation
export function usePauseWatchfolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (folderId: string): Promise<ActionResponse> => {
      const { data } = await apiClient.post<ActionResponse>(`/watchfolders/${folderId}/pause`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchfolders'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Resume watchfolder mutation
export function useResumeWatchfolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (folderId: string): Promise<ActionResponse> => {
      const { data } = await apiClient.post<ActionResponse>(`/watchfolders/${folderId}/resume`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchfolders'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}
