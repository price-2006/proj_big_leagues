import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useCreateMatch } from '../api/hooks/useMatch'
import { ScoreBreakdown } from '../components/ScoreBreakdown/ScoreBreakdown'
import { SkillBadgeList } from '../components/SkillBadgeList/SkillBadgeList'

export function MatchResults() {
  const [searchParams] = useSearchParams()
  const resumeId = searchParams.get('resumeId')
  const jobId = searchParams.get('jobId')
  const createMatch = useCreateMatch()

  useEffect(() => {
    // POST /matches is idempotent for a given (resume, job, scoring
    // version) — safe to call on every visit rather than needing a
    // separate "does a match already exist" check.
    if (resumeId && jobId) {
      createMatch.mutate({ resumeId, jobId })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, jobId])

  if (!resumeId || !jobId) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-slate-500">Missing resume or job — start from the resume upload page.</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Match results</h1>

      {createMatch.isPending && <p className="text-slate-500">Computing match…</p>}

      {createMatch.isError && (
        <p className="rounded-md bg-rose-50 px-4 py-3 text-rose-700">
          {createMatch.error instanceof Error ? createMatch.error.message : 'Could not compute a match.'}
        </p>
      )}

      {createMatch.isSuccess && createMatch.data && (
        <div className="space-y-8">
          <div className="rounded-lg border border-slate-200 p-5">
            <ScoreBreakdown
              ruleBasedScore={createMatch.data.rule_based_score}
              features={createMatch.data.feature_vector}
            />
          </div>
          <div className="rounded-lg border border-slate-200 p-5">
            <SkillBadgeList breakdown={createMatch.data.skill_breakdown} />
          </div>
          <div className="flex gap-4">
            <Link
              to={`/resume/optimize?resumeId=${resumeId}&jobId=${jobId}`}
              className="rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700"
            >
              Get AI recommendations
            </Link>
            <Link
              to={`/jobs/compare?resumeId=${resumeId}`}
              className="rounded-md border border-slate-300 px-4 py-2 text-slate-700 font-medium hover:bg-slate-50"
            >
              Compare with other jobs
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
