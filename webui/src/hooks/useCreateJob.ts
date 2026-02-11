import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { EncodingRequest, SubmitJobResponse } from '../api/types'

export function useSubmitJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: EncodingRequest): Promise<SubmitJobResponse> => {
      const { data } = await apiClient.post<SubmitJobResponse>('/jobs', {
        request,
      })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })
}
