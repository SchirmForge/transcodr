import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type {
  ProfilesResponse,
  ProfileInfo,
  BuiltinsResponse,
  BuiltinProfileEntry,
  ImportBuiltinsRequest,
  ImportBuiltinsResponse,
} from '../api/types'

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

// Fetch installable builtin profiles
export function useBuiltinProfiles() {
  return useQuery({
    queryKey: ['profiles', 'builtins'],
    queryFn: async (): Promise<BuiltinProfileEntry[]> => {
      const { data } = await apiClient.get<BuiltinsResponse>('/profiles/builtins/list')
      return data.builtins
    },
  })
}

// Import selected builtin profiles into user dir
export function useImportBuiltins() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      names,
      overwrite = false,
    }: ImportBuiltinsRequest & { overwrite?: boolean }): Promise<ImportBuiltinsResponse> => {
      const url = overwrite
        ? '/profiles/import-builtins?overwrite=true'
        : '/profiles/import-builtins'
      const { data } = await apiClient.post<ImportBuiltinsResponse>(url, { names })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
    },
  })
}
