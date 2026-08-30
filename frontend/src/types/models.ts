// Convenience re-exports so callers write `MatchResponse` instead of
// `components['schemas']['MatchResponse']` everywhere.
import type { components } from './api'

export type CandidateProfile = components['schemas']['CandidateProfile']
export type JobProfile = components['schemas']['JobProfile']
export type ResumeResponse = components['schemas']['ResumeResponse']
export type JobResponse = components['schemas']['JobResponse']
export type MatchResponse = components['schemas']['MatchResponse']
export type FeatureVector = components['schemas']['FeatureVector']
export type SkillBreakdown = components['schemas']['SkillBreakdown']
export type RequirementItem = components['schemas']['RequirementItem']
