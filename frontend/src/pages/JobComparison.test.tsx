// Phase 13 test procedure per docs/ROADMAP.md ("ranking order matches the
// stored scores") — unit tests for the pure ranking/opportunity logic.
// Full-page rendering (React Query + router + session context) is
// exercised via the manual walkthrough the roadmap's own Test line
// prescribes, matching this codebase's existing pattern of not having
// full page-render tests for any other page (Dashboard/MatchResults/etc).
import { describe, expect, it } from 'vitest'

import type { MatchResponse, SkillBreakdown } from '../types/models'
import { findBiggestOpportunity, rankMatchesByScore } from './JobComparison'

function match(overrides: Partial<MatchResponse> & { id: string; job_id: string }): MatchResponse {
  const breakdown: SkillBreakdown = { matched_required: [], missing_required: [], matched_preferred: [], missing_preferred: [] }
  return {
    resume_id: 'r1',
    feature_vector: {
      required_skill_coverage: 0,
      preferred_skill_coverage: 0,
      semantic_experience_similarity: 0,
      project_relevance_similarity: 0,
      education_match: 0,
      years_experience_match: 0,
      domain_similarity: 0,
      responsibility_similarity: 0,
      seniority_match: 0,
      skill_importance_weighted_score: 0,
    },
    skill_breakdown: breakdown,
    rule_based_score: 0,
    ml_score: null,
    scoring_model_version: 'v1',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('rankMatchesByScore', () => {
  it('sorts descending by rule_based_score', () => {
    const matches = [
      match({ id: 'a', job_id: 'j1', rule_based_score: 40 }),
      match({ id: 'b', job_id: 'j2', rule_based_score: 90 }),
      match({ id: 'c', job_id: 'j3', rule_based_score: 65 }),
    ]
    const ranked = rankMatchesByScore(matches)
    expect(ranked.map((m) => m.id)).toEqual(['b', 'c', 'a'])
  })

  it('does not mutate the input array', () => {
    const matches = [match({ id: 'a', job_id: 'j1', rule_based_score: 40 }), match({ id: 'b', job_id: 'j2', rule_based_score: 90 })]
    const original = [...matches]
    rankMatchesByScore(matches)
    expect(matches).toEqual(original)
  })
})

describe('findBiggestOpportunity', () => {
  it('picks the non-best match with the fewest missing required skills', () => {
    const matches = [
      match({ id: 'best', job_id: 'j1', rule_based_score: 90, skill_breakdown: { matched_required: [], missing_required: [], matched_preferred: [], missing_preferred: [] } }),
      match({ id: 'far', job_id: 'j2', rule_based_score: 50, skill_breakdown: { matched_required: [], missing_required: ['A', 'B', 'C'], matched_preferred: [], missing_preferred: [] } }),
      match({ id: 'close', job_id: 'j3', rule_based_score: 60, skill_breakdown: { matched_required: [], missing_required: ['A'], matched_preferred: [], missing_preferred: [] } }),
    ]
    const opportunity = findBiggestOpportunity(matches, 'best')
    expect(opportunity?.id).toBe('close')
  })

  it('excludes the best match itself even if it has missing skills', () => {
    const matches = [
      match({ id: 'best', job_id: 'j1', rule_based_score: 90, skill_breakdown: { matched_required: [], missing_required: ['A'], matched_preferred: [], missing_preferred: [] } }),
    ]
    expect(findBiggestOpportunity(matches, 'best')).toBeNull()
  })

  it('excludes candidates with zero missing required skills — nothing to "close"', () => {
    const matches = [
      match({ id: 'best', job_id: 'j1', rule_based_score: 90 }),
      match({ id: 'also-perfect', job_id: 'j2', rule_based_score: 70, skill_breakdown: { matched_required: [], missing_required: [], matched_preferred: [], missing_preferred: [] } }),
    ]
    expect(findBiggestOpportunity(matches, 'best')).toBeNull()
  })

  it('returns null when there are no other matches', () => {
    expect(findBiggestOpportunity([], undefined)).toBeNull()
  })
})
