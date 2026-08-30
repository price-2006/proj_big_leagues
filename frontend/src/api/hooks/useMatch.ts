import { useMutation, useQuery } from '@tanstack/react-query'

import { apiClient } from '../client'

export function useCreateMatch() {
  return useMutation({
    mutationFn: async ({ resumeId, jobId }: { resumeId: string; jobId: string }) => {
      const { data, error } = await apiClient.POST('/api/v1/matches', {
        body: { resume_id: resumeId, job_id: jobId },
      })
      if (error) throw error
      return data
    },
  })
}

export function useMatch(matchId: string | undefined) {
  return useQuery({
    queryKey: ['match', matchId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/matches/{match_id}', {
        params: { path: { match_id: matchId! } },
      })
      if (error) throw error
      return data
    },
    enabled: !!matchId,
  })
}
