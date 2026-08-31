import { Link } from 'react-router-dom'

import { useResumeMatches } from '../api/hooks/useResume'
import { useSession } from '../context/SessionContext'

export function Dashboard() {
  const { resumes, jobs } = useSession()
  // MVP scope: stats are computed for the most recently uploaded resume.
  // Aggregating across every tracked resume would need a batch of hook
  // calls (one per resume), which isn't a great fit for the common
  // single-resume-many-jobs flow this phase targets — JobComparison.tsx
  // (Phase 13) is the real multi-*job* ranking view for that one resume,
  // linked below.
  const primaryResume = resumes[0]
  const matches = useResumeMatches(primaryResume?.id)

  const scores = matches.data?.map((m) => m.rule_based_score) ?? []
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null
  const topMatch = matches.data?.length
    ? matches.data.reduce((best, m) => (m.rule_based_score > best.rule_based_score ? m : best))
    : null

  const gapCounts = new Map<string, number>()
  for (const match of matches.data ?? []) {
    for (const skill of match.skill_breakdown.missing_required) {
      gapCounts.set(skill, (gapCounts.get(skill) ?? 0) + 1)
    }
  }
  const commonGaps = [...gapCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <Stat label="Resumes uploaded" value={resumes.length} />
        <Stat label="Jobs analyzed" value={jobs.length} />
        <Stat label="Avg. match score" value={avgScore !== null ? `${Math.round(avgScore)}%` : '—'} />
        <Stat label="Top match" value={topMatch ? `${Math.round(topMatch.rule_based_score)}%` : '—'} />
      </div>

      {primaryResume && matches.data && matches.data.length > 1 && (
        <p className="mb-8 text-sm">
          <Link to={`/jobs/compare?resumeId=${primaryResume.id}`} className="text-indigo-600 hover:underline">
            Compare all {matches.data.length} jobs against this resume →
          </Link>
        </p>
      )}

      {commonGaps.length > 0 && (
        <div className="mb-8 rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Common skill gaps</h2>
          <p className="text-sm text-slate-500 mb-3">Required skills missing across your analyzed jobs.</p>
          <div className="flex flex-wrap gap-2">
            {commonGaps.map(([skill, count]) => (
              <span key={skill} className="rounded-full bg-rose-50 px-3 py-1 text-sm text-rose-700 ring-1 ring-rose-200">
                {skill} × {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {resumes.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-6 sm:grid-cols-2">
          <ResumeList resumes={resumes} />
          <JobList jobs={jobs} />
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center">
      <p className="text-slate-500 mb-4">Nothing here yet — upload a resume to get started.</p>
      <Link to="/resume/upload" className="rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700">
        Upload a resume
      </Link>
    </div>
  )
}

function ResumeList({ resumes }: { resumes: { id: string; name: string | null; filename: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-200 p-5">
      <h2 className="font-semibold text-slate-900 mb-3">Resumes</h2>
      <ul className="space-y-2 text-sm">
        {resumes.map((resume) => (
          <li key={resume.id}>
            <Link to={`/jobs/new?resumeId=${resume.id}`} className="text-indigo-600 hover:underline">
              {resume.name ?? resume.filename}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function JobList({ jobs }: { jobs: { id: string; title: string | null }[] }) {
  return (
    <div className="rounded-lg border border-slate-200 p-5">
      <h2 className="font-semibold text-slate-900 mb-3">Jobs analyzed</h2>
      <ul className="space-y-2 text-sm text-slate-700">
        {jobs.map((job) => (
          <li key={job.id}>{job.title ?? 'Untitled role'}</li>
        ))}
      </ul>
    </div>
  )
}
