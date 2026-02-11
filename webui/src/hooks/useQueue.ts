import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { ActionResponse } from '../api/types'

// Pause queue
export function usePauseQueue() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<ActionResponse> => {
      const { data } = await apiClient.post<ActionResponse>('/queue/pause')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Resume queue
export function useResumeQueue() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<ActionResponse> => {
      const { data } = await apiClient.post<ActionResponse>('/queue/resume')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Clear completed jobs
export function useClearCompleted() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<ActionResponse> => {
      const { data } = await apiClient.delete<ActionResponse>('/queue/completed')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Clear failed jobs
export function useClearFailed() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<ActionResponse> => {
      const { data } = await apiClient.delete<ActionResponse>('/queue/failed')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Clear warning jobs (completed with warnings)
export function useClearWarning() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<ActionResponse> => {
      const { data } = await apiClient.delete<ActionResponse>('/queue/warning')
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}
