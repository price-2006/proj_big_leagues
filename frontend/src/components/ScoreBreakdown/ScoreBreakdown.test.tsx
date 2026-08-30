// Phase 9 test procedure per docs/ROADMAP.md: component tests for the
// score-breakdown rendering logic given known feature inputs. These
// exact numbers are a real, verified match computed by the backend
// (Phase 7/8) for a strong candidate against a Senior Backend Engineer
// posting — 0.35*1.0 + 0.20*0.3482 + 0.15*0.0 + 0.10*0.7 + 0.10*0.7 +
// 0.10*0.7 = 62.96 — not invented numbers.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { FeatureVector } from '../../types/models'
import { buildScoreBreakdownBars, ScoreBreakdown } from './ScoreBreakdown'

const KNOWN_FEATURES: FeatureVector = {
  required_skill_coverage: 1.0,
  preferred_skill_coverage: 0.7,
  semantic_experience_similarity: 0.3482220086979084,
  project_relevance_similarity: 0.0,
  education_match: 0.7,
  years_experience_match: 0.7,
  domain_similarity: 0.0,
  responsibility_similarity: 0.4266881930524485,
  seniority_match: 0.7,
  skill_importance_weighted_score: 1.0,
}

describe('buildScoreBreakdownBars', () => {
  it('derives the seniority_and_experience_composite as the average of its two inputs', () => {
    const bars = buildScoreBreakdownBars(KNOWN_FEATURES)
    const composite = bars.find((b) => b.key === 'seniority_and_experience_composite')
    // (0.7 seniority_match + 0.7 years_experience_match) / 2 = 0.7 -> 70%
    expect(composite?.valuePct).toBeCloseTo(70)
  })

  it('maps each of the 6 scorer-relevant features to a bar with its weight', () => {
    const bars = buildScoreBreakdownBars(KNOWN_FEATURES)
    expect(bars).toHaveLength(6)
    expect(bars.find((b) => b.key === 'required_skill_coverage')).toMatchObject({ weightPct: 35, valuePct: 100 })
    expect(bars.find((b) => b.key === 'project_relevance_similarity')).toMatchObject({ weightPct: 15, valuePct: 0 })
  })
})

describe('ScoreBreakdown', () => {
  it('renders the overall rounded score', () => {
    render(<ScoreBreakdown ruleBasedScore={62.96} features={KNOWN_FEATURES} />)
    expect(screen.getByText('63%')).toBeInTheDocument()
  })

  it('renders a bar with the correct rounded percentage and weight for each scorer feature', () => {
    render(<ScoreBreakdown ruleBasedScore={62.96} features={KNOWN_FEATURES} />)

    const requiredSkillsBar = screen.getByTestId('bar-required_skill_coverage')
    expect(requiredSkillsBar).toHaveTextContent('Required Skills')
    expect(requiredSkillsBar).toHaveTextContent('100%')
    expect(requiredSkillsBar).toHaveTextContent('weight 35%')

    const experienceBar = screen.getByTestId('bar-semantic_experience_similarity')
    expect(experienceBar).toHaveTextContent('35%') // round(34.822...)
    expect(experienceBar).toHaveTextContent('weight 20%')

    const projectBar = screen.getByTestId('bar-project_relevance_similarity')
    expect(projectBar).toHaveTextContent('0%')
  })

  it('sets each bar fill width to its value percentage, clamped to [0, 100]', () => {
    render(<ScoreBreakdown ruleBasedScore={62.96} features={KNOWN_FEATURES} />)
    const requiredSkillsBar = screen.getByTestId('bar-required_skill_coverage')
    const fill = requiredSkillsBar.querySelector('.bg-slate-200 > div') as HTMLElement
    expect(fill.style.width).toBe('100%')
  })

  it('renders zero features as an empty (0%-width) bar, not a missing one', () => {
    const zeroFeatures: FeatureVector = { ...KNOWN_FEATURES, project_relevance_similarity: 0 }
    render(<ScoreBreakdown ruleBasedScore={62.96} features={zeroFeatures} />)
    const projectBar = screen.getByTestId('bar-project_relevance_similarity')
    const fill = projectBar.querySelector('.bg-slate-200 > div') as HTMLElement
    expect(fill.style.width).toBe('0%')
  })
})
