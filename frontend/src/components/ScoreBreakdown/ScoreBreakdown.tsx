import type { FeatureVector } from '../../types/models'

// Mirrors the 6 weighted terms in backend/app/ml/rule_based_scorer.py's
// DEFAULT_WEIGHTS exactly — including the seniority_and_experience_composite
// derivation — so the bars always sum to what rule_based_score actually is.
// The other 4 of the 10 stored features (domain_similarity,
// responsibility_similarity, skill_importance_weighted_score) aren't shown
// here because the score itself doesn't use them (see that module's
// docstring) — showing them here would misleadingly imply they moved the
// number.
const WEIGHTS = {
  required_skill_coverage: 0.35,
  semantic_experience_similarity: 0.2,
  project_relevance_similarity: 0.15,
  preferred_skill_coverage: 0.1,
  education_match: 0.1,
  seniority_and_experience_composite: 0.1,
} as const

interface Bar {
  key: string
  label: string
  weightPct: number
  valuePct: number
}

export function buildScoreBreakdownBars(features: FeatureVector): Bar[] {
  const seniorityAndExperienceComposite = (features.seniority_match + features.years_experience_match) / 2

  return [
    { key: 'required_skill_coverage', label: 'Required Skills', weightPct: WEIGHTS.required_skill_coverage * 100, valuePct: features.required_skill_coverage * 100 },
    { key: 'semantic_experience_similarity', label: 'Experience Relevance', weightPct: WEIGHTS.semantic_experience_similarity * 100, valuePct: features.semantic_experience_similarity * 100 },
    { key: 'project_relevance_similarity', label: 'Project Relevance', weightPct: WEIGHTS.project_relevance_similarity * 100, valuePct: features.project_relevance_similarity * 100 },
    { key: 'preferred_skill_coverage', label: 'Preferred Skills', weightPct: WEIGHTS.preferred_skill_coverage * 100, valuePct: features.preferred_skill_coverage * 100 },
    { key: 'education_match', label: 'Education', weightPct: WEIGHTS.education_match * 100, valuePct: features.education_match * 100 },
    { key: 'seniority_and_experience_composite', label: 'Seniority & Experience', weightPct: WEIGHTS.seniority_and_experience_composite * 100, valuePct: seniorityAndExperienceComposite * 100 },
  ]
}

function barColor(valuePct: number): string {
  if (valuePct >= 70) return 'bg-emerald-500'
  if (valuePct >= 40) return 'bg-amber-500'
  return 'bg-rose-500'
}

interface ScoreBreakdownProps {
  ruleBasedScore: number // 0-100
  features: FeatureVector
}

export function ScoreBreakdown({ ruleBasedScore, features }: ScoreBreakdownProps) {
  const bars = buildScoreBreakdownBars(features)

  return (
    <div className="space-y-4" data-testid="score-breakdown">
      <div className="flex items-baseline gap-2">
        <span className="text-4xl font-bold text-slate-900">{Math.round(ruleBasedScore)}%</span>
        <span className="text-sm text-slate-500">rule-based match score</span>
      </div>
      <div className="space-y-3">
        {bars.map((bar) => (
          <div key={bar.key} data-testid={`bar-${bar.key}`}>
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium text-slate-700">{bar.label}</span>
              <span className="text-slate-500">
                {Math.round(bar.valuePct)}%{' '}
                <span className="text-slate-400">(weight {Math.round(bar.weightPct)}%)</span>
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-200">
              <div
                className={`h-2 rounded-full ${barColor(bar.valuePct)}`}
                style={{ width: `${Math.min(Math.max(bar.valuePct, 0), 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
