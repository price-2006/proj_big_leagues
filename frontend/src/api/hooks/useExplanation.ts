import { useMutation } from '@tanstack/react-query'

import { apiClient } from '../client'

// A mutation, not a query — POST /resumes/{id}/recommendations, matching
// useCreateMatch's pattern (Phase 8). It's idempotent server-side (the
// backend returns the stored explanation on a second call rather than
// re-calling the LLM — app/services/explanation_service.py), so calling
// it on page mount, the same way MatchResults.tsx calls useCreateMatch, is safe.
export function useGenerateRecommendations() {
  return useMutation({
    mutationFn: async ({ resumeId, jobId }: { resumeId: string; jobId: string }) => {
      const { data, error } = await apiClient.POST('/api/v1/resumes/{resume_id}/recommendations', {
        params: { path: { resume_id: resumeId }, query: { job_id: jobId } },
      })
      if (error) throw error
      return data
    },
  })
}
