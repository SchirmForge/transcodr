import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { JobInfo, JobListResponse, ActionResponse } from '../api/types'

// Fetch active jobs (running, pending, queued)
export function useActiveJobs() {
  return useQuery({
    queryKey: ['jobs', 'active'],
    queryFn: async (): Promise<JobInfo[]> => {
      const [running, pending, queued] = await Promise.all([
        apiClient.get<JobListResponse>('/jobs', { params: { status: 'running' } }),
        apiClient.get<JobListResponse>('/jobs', { params: { status: 'pending' } }),
        apiClient.get<JobListResponse>('/jobs', { params: { status: 'queued' } }),
      ])
      return [
        ...running.data.jobs,
        ...pending.data.jobs,
        ...queued.data.jobs,
      ]
    },
  })
}

// Fetch history jobs (completed, failed)
export function useHistoryJobs() {
  return useQuery({
    queryKey: ['jobs', 'history'],
    queryFn: async (): Promise<JobInfo[]> => {
      const [completed, failed] = await Promise.all([
        apiClient.get<JobListResponse>('/jobs', { params: { status: 'completed' } }),
        apiClient.get<JobListResponse>('/jobs', { params: { status: 'failed' } }),
      ])
      return [...failed.data.jobs, ...completed.data.jobs]
    },
  })
}

// Fetch single job by ID
export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async (): Promise<JobInfo> => {
      const { data } = await apiClient.get<JobInfo>(`/jobs/${jobId}`)
      return data
    },
    enabled: !!jobId,
  })
}

// Cancel job mutation
export function useCancelJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (jobId: string): Promise<ActionResponse> => {
      const { data } = await apiClient.delete<ActionResponse>(`/jobs/${jobId}`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}

// Retry failed job mutation
export function useRetryJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (jobId: string): Promise<JobInfo> => {
      const { data } = await apiClient.post<JobInfo>(`/jobs/${jobId}/retry`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}
