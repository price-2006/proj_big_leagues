import { Link, useSearchParams } from 'react-router-dom'

import { useResumeMatches } from '../api/hooks/useResume'
import { useSession } from '../context/SessionContext'
import type { MatchResponse } from '../types/models'

export function rankMatchesByScore(matches: MatchResponse[]): MatchResponse[] {
  return [...matches].sort((a, b) => b.rule_based_score - a.rule_based_score)
}

// "Biggest opportunity": not just "next-highest score" — the job (other
// than the best match) with the FEWEST missing required skills, i.e.
// closest to becoming a great match if just a couple of gaps get closed.
// A job with zero missing skills isn't "an opportunity to close a gap",
// so it's excluded — that's just already a fine match, scored lower for
// other reasons.
export function findBiggestOpportunity(matches: MatchResponse[], bestMatchId: string | undefined): MatchResponse | null {
  const candidates = matches.filter((m) => m.id !== bestMatchId && m.skill_breakdown.missing_required.length > 0)
  if (candidates.length === 0) return null
  return candidates.reduce((best, m) =>
    m.skill_breakdown.missing_required.length < best.skill_breakdown.missing_required.length ? m : best,
  )
}

export function JobComparison() {
  const [searchParams] = useSearchParams()
  const resumeId = searchParams.get('resumeId')
  const { jobs } = useSession()
  const matches = useResumeMatches(resumeId ?? undefined)

  if (!resumeId) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-slate-500">Missing resume — start from the resume upload page.</p>
      </div>
    )
  }

  const jobTitle = (jobId: string) => jobs.find((j) => j.id === jobId)?.title ?? 'Untitled role'

  const ranked = rankMatchesByScore(matches.data ?? [])
  const bestMatch = ranked[0]
  const biggestOpportunity = findBiggestOpportunity(ranked, bestMatch?.id)

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Compare jobs</h1>
      <p className="text-slate-500 mb-6">Every job analyzed against this resume, ranked by match score.</p>

      {matches.isPending && <p className="text-slate-500">Loading matches…</p>}

      {matches.isSuccess && ranked.length === 0 && (
        <p className="text-slate-500">
          No matches yet.{' '}
          <Link to={`/jobs/new?resumeId=${resumeId}`} className="text-indigo-600 hover:underline">
            Analyze a job
          </Link>{' '}
          to get started.
        </p>
      )}

      {ranked.length > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 mb-8">
            {bestMatch && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                <div className="text-xs font-semibold uppercase text-emerald-700 mb-1">Best match</div>
                <div className="font-semibold text-slate-900">{jobTitle(bestMatch.job_id)}</div>
                <div className="text-2xl font-bold text-slate-900">{Math.round(bestMatch.rule_based_score)}%</div>
              </div>
            )}
            {biggestOpportunity && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <div className="text-xs font-semibold uppercase text-amber-700 mb-1">Biggest opportunity</div>
                <div className="font-semibold text-slate-900">{jobTitle(biggestOpportunity.job_id)}</div>
                <div className="text-sm text-slate-600">
                  {biggestOpportunity.skill_breakdown.missing_required.length} skill
                  {biggestOpportunity.skill_breakdown.missing_required.length === 1 ? '' : 's'} away:{' '}
                  {biggestOpportunity.skill_breakdown.missing_required.join(', ')}
                </div>
              </div>
            )}
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Job</th>
                  <th className="px-4 py-2 font-medium">Score</th>
                  <th className="px-4 py-2 font-medium">Missing required</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((match) => (
                  <tr key={match.id} className="border-t border-slate-100">
                    <td className="px-4 py-3 text-slate-900">{jobTitle(match.job_id)}</td>
                    <td className="px-4 py-3 font-semibold text-slate-900">{Math.round(match.rule_based_score)}%</td>
                    <td className="px-4 py-3 text-slate-600">{match.skill_breakdown.missing_required.length}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/resume/optimize?resumeId=${resumeId}&jobId=${match.job_id}`}
                        className="text-indigo-600 hover:underline"
                      >
                        Get recommendations
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
