import { useMutation, useQuery } from '@tanstack/react-query'

import { apiClient } from '../client'

export function useUploadResume() {
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const { data, error } = await apiClient.POST('/api/v1/resumes', {
        // openapi-fetch passes FormData straight through as the multipart body.
        body: formData as never,
      })
      if (error) throw error
      return data
    },
  })
}

export function useResume(resumeId: string | undefined) {
  return useQuery({
    queryKey: ['resume', resumeId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/resumes/{resume_id}', {
        params: { path: { resume_id: resumeId! } },
      })
      if (error) throw error
      return data
    },
    enabled: !!resumeId,
  })
}

export function useResumeMatches(resumeId: string | undefined) {
  return useQuery({
    queryKey: ['resume-matches', resumeId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/resumes/{resume_id}/matches', {
        params: { path: { resume_id: resumeId! } },
      })
      if (error) throw error
      return data
    },
    enabled: !!resumeId,
  })
}
