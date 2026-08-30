import type { SkillBreakdown } from '../../types/models'

function Badge({ text, variant }: { text: string; variant: 'matched' | 'missing' }) {
  const classes =
    variant === 'matched'
      ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
      : 'bg-rose-50 text-rose-700 ring-1 ring-rose-200'
  return <span className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${classes}`}>{text}</span>
}

function SkillGroup({ title, matched, missing }: { title: string; matched: string[]; missing: string[] }) {
  if (matched.length === 0 && missing.length === 0) return null
  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-600 mb-2">{title}</h4>
      <div className="flex flex-wrap gap-2">
        {matched.map((skill) => (
          <Badge key={`matched-${skill}`} text={skill} variant="matched" />
        ))}
        {missing.map((skill) => (
          <Badge key={`missing-${skill}`} text={skill} variant="missing" />
        ))}
      </div>
    </div>
  )
}

interface SkillBadgeListProps {
  breakdown: SkillBreakdown
}

export function SkillBadgeList({ breakdown }: SkillBadgeListProps) {
  return (
    <div className="space-y-4" data-testid="skill-badge-list">
      <SkillGroup title="Required skills" matched={breakdown.matched_required} missing={breakdown.missing_required} />
      <SkillGroup
        title="Preferred skills"
        matched={breakdown.matched_preferred}
        missing={breakdown.missing_preferred}
      />
    </div>
  )
}
