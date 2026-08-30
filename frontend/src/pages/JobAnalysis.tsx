import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { useCreateJob } from '../api/hooks/useJob'
import { useSession } from '../context/SessionContext'

export function JobAnalysis() {
  const [searchParams] = useSearchParams()
  const resumeId = searchParams.get('resumeId')
  const navigate = useNavigate()

  const [rawText, setRawText] = useState('')
  const createJob = useCreateJob()
  const { addJob } = useSession()

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!rawText.trim()) return
    createJob.mutate(
      { rawText },
      {
        onSuccess: (job) => {
          if (!job) return
          addJob({ id: job.id, title: job.title })
        },
      },
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Analyze a job description</h1>
      <p className="text-slate-500 mb-6">Paste the full posting text — we'll split out required vs. preferred requirements.</p>

      <form onSubmit={onSubmit}>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          rows={12}
          placeholder="Paste the job description here…"
          className="w-full rounded-md border border-slate-300 p-3 text-sm focus:border-indigo-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!rawText.trim() || createJob.isPending}
          className="mt-3 rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {createJob.isPending ? 'Analyzing…' : 'Analyze'}
        </button>
      </form>

      {createJob.isError && (
        <p className="mt-4 rounded-md bg-rose-50 px-4 py-3 text-rose-700">
          {createJob.error instanceof Error ? createJob.error.message : 'Could not parse that job description.'}
        </p>
      )}

      {createJob.isSuccess && createJob.data && (
        <div className="mt-6 rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900">{createJob.data.title ?? 'Untitled role'}</h2>
          <p className="text-sm text-slate-500 mb-4 capitalize">
            Seniority: {createJob.data.parsed_profile.seniority}
          </p>

          <h3 className="text-sm font-semibold text-slate-600 mb-2">Required</h3>
          <ul className="mb-4 space-y-1 text-sm text-slate-700">
            {createJob.data.parsed_profile.requirements
              .filter((r) => r.level === 'required')
              .map((r) => (
                <li key={r.text} className="border-l-2 border-rose-300 pl-2">
                  {r.text}
                </li>
              ))}
          </ul>

          <h3 className="text-sm font-semibold text-slate-600 mb-2">Preferred</h3>
          <ul className="mb-4 space-y-1 text-sm text-slate-700">
            {createJob.data.parsed_profile.requirements
              .filter((r) => r.level === 'preferred')
              .map((r) => (
                <li key={r.text} className="border-l-2 border-emerald-300 pl-2">
                  {r.text}
                </li>
              ))}
          </ul>

          {resumeId ? (
            <button
              onClick={() => navigate(`/matches/new?resumeId=${resumeId}&jobId=${createJob.data.id}`)}
              className="rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700"
            >
              See match results
            </button>
          ) : (
            <p className="text-sm text-slate-500">
              <Link to="/resume/upload" className="text-indigo-600 hover:underline">
                Upload a resume
              </Link>{' '}
              to see how well it matches this role.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
