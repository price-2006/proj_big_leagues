import { useMutation, useQuery } from '@tanstack/react-query'

import { apiClient } from '../client'

interface CreateJobInput {
  rawText?: string
  file?: File
  title?: string
  company?: string
}

export function useCreateJob() {
  return useMutation({
    mutationFn: async ({ rawText, file, title, company }: CreateJobInput) => {
      const formData = new FormData()
      if (rawText) formData.append('raw_text', rawText)
      if (file) formData.append('file', file)
      if (title) formData.append('title', title)
      if (company) formData.append('company', company)

      const { data, error } = await apiClient.POST('/api/v1/jobs', {
        body: formData as never,
      })
      if (error) throw error
      return data
    },
  })
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/jobs/{job_id}', {
        params: { path: { job_id: jobId! } },
      })
      if (error) throw error
      return data
    },
    enabled: !!jobId,
  })
}
