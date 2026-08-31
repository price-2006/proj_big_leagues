import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useGenerateRecommendations } from '../api/hooks/useExplanation'
import { EvidencePopover } from '../components/EvidencePopover/EvidencePopover'
import type { EvidencedClaimResponse } from '../types/models'

function Chip({ text, variant }: { text: string; variant: 'match' | 'gap' | 'partial' }) {
  const classes = {
    match: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
    gap: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
    partial: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  }[variant]
  return <span className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${classes}`}>{text}</span>
}

function ClaimList({ claims }: { claims: EvidencedClaimResponse[] }) {
  if (claims.length === 0) return <p className="text-sm text-slate-400">None grounded enough to show.</p>
  return (
    <ul className="space-y-3">
      {claims.map((claim, i) => (
        <li key={i}>
          <EvidencePopover text={claim.text} evidenceText={claim.evidence_text} isInference={claim.is_inference} />
        </li>
      ))}
    </ul>
  )
}

export function ResumeOptimization() {
  const [searchParams] = useSearchParams()
  const resumeId = searchParams.get('resumeId')
  const jobId = searchParams.get('jobId')
  const generate = useGenerateRecommendations()

  useEffect(() => {
    // Idempotent server-side (app/services/explanation_service.py) —
    // safe to call on every visit, same reasoning as MatchResults.tsx's
    // useCreateMatch.
    if (resumeId && jobId) {
      generate.mutate({ resumeId, jobId })
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
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Resume optimization</h1>
      <p className="text-slate-500 mb-6">AI-generated, evidence-grounded strengths, gaps, and suggestions for this pairing.</p>

      {generate.isPending && <p className="text-slate-500">Generating recommendations…</p>}

      {generate.isError && (
        <p className="rounded-md bg-rose-50 px-4 py-3 text-rose-700">
          {generate.error instanceof Error ? generate.error.message : 'Could not generate recommendations.'}
        </p>
      )}

      {generate.isSuccess && generate.data && (
        <div className="space-y-8">
          {generate.data.narrative && (
            <div className="rounded-lg border border-slate-200 p-5">
              <p className="text-sm text-slate-700">{generate.data.narrative}</p>
            </div>
          )}

          <div className="rounded-lg border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-900 mb-3">Skills</h2>
            <div className="flex flex-wrap gap-2">
              {generate.data.matching_skills.map((s) => (
                <Chip key={`match-${s}`} text={s} variant="match" />
              ))}
              {generate.data.missing_skills.map((s) => (
                <Chip key={`gap-${s}`} text={s} variant="gap" />
              ))}
              {generate.data.partial_skills.map((s) => (
                <Chip key={`partial-${s}`} text={s} variant="partial" />
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-900 mb-3">Strengths</h2>
            <ClaimList claims={generate.data.strengths} />
          </div>

          <div className="rounded-lg border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-900 mb-3">Weaknesses</h2>
            <ClaimList claims={generate.data.weaknesses} />
          </div>

          <div className="rounded-lg border border-slate-200 p-5">
            <h2 className="font-semibold text-slate-900 mb-3">Recommendations</h2>
            {generate.data.recommendations.length === 0 ? (
              <p className="text-sm text-slate-400">None grounded enough to show.</p>
            ) : (
              <ul className="space-y-3">
                {generate.data.recommendations.map((rec, i) => (
                  <li key={i}>
                    <EvidencePopover text={rec.suggestion} evidenceText={rec.evidence_text} isInference={false} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!generate.data.evidence_check_passed && (
            <p className="text-xs text-slate-400">
              Some claims from the AI's original response couldn't be verified against the resume/job description and
              were removed rather than shown unchecked.
            </p>
          )}
          {generate.data.llm_model && <p className="text-xs text-slate-400">Generated by {generate.data.llm_model}.</p>}
        </div>
      )}
    </div>
  )
}
