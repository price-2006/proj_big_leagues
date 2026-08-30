"""(resume, job) -> stored Match row (Phase 8). Orchestrates Phases 5-7:
skill taxonomy + embeddings -> the 10-feature vector -> rule-based score
-> persist. Idempotent within a scoring_model_version: computing the same
pair twice returns the existing row rather than recomputing (the
embedding calls aren't free, and the result would be identical anyway
since it's a pure function of the stored profiles + weights).

The insert itself is a conflict-safe upsert, not a plain INSERT after a
"does it exist" SELECT — two concurrent identical requests (verified
live: React StrictMode intentionally double-invokes effects in dev mode,
which double-fired POST /matches for the same pair) can both pass that
SELECT before either commits, and a plain INSERT then raises
UniqueViolationError on the second one. ON CONFLICT DO NOTHING makes the
race safe instead of a 500.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_engineering import compute_feature_vector, compute_skill_breakdown
from app.ml.rule_based_scorer import score
from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile
from app.schemas.match_features import SkillBreakdown
from app.services.embedding_service import EmbeddingService
from app.services.scoring_weights_store import load_active_weights
from app.services.skill_normalization_service import SkillTaxonomy


class ResumeNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


async def compute_and_store_match(
    session: AsyncSession,
    resume_id: uuid.UUID,
    job_id: uuid.UUID,
    taxonomy: SkillTaxonomy,
    embedding_service: EmbeddingService,
) -> Match:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise ResumeNotFoundError(resume_id)
    job = await session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(job_id)

    version, weights = await load_active_weights(session)

    existing_match = await _find_match(session, resume_id, job_id, version)
    if existing_match is not None:
        return existing_match

    candidate = CandidateProfile.model_validate(resume.parsed_profile)
    job_profile = JobProfile.model_validate(job.parsed_profile)
    features = compute_feature_vector(candidate, job_profile, taxonomy, embedding_service, as_of=date.today())
    rule_based_score = score(features, weights)

    stmt = (
        pg_insert(Match)
        .values(
            resume_id=resume_id,
            job_id=job_id,
            feature_vector=features.model_dump(mode="json"),
            rule_based_score=Decimal(str(round(rule_based_score * 100, 2))),
            scoring_model_version=version,
        )
        .on_conflict_do_nothing(index_elements=["resume_id", "job_id", "scoring_model_version"])
        .returning(Match.id)
    )
    result = await session.execute(stmt)
    await session.flush()
    inserted_id = result.scalar_one_or_none()

    if inserted_id is None:
        # Lost the race to a concurrent identical request — its row is
        # the answer, not an error.
        existing_match = await _find_match(session, resume_id, job_id, version)
        assert existing_match is not None, "insert conflicted but no row found — should be unreachable"
        return existing_match

    return await session.get(Match, inserted_id)


async def _find_match(session: AsyncSession, resume_id: uuid.UUID, job_id: uuid.UUID, version: str) -> Match | None:
    result = await session.execute(
        select(Match).where(
            Match.resume_id == resume_id, Match.job_id == job_id, Match.scoring_model_version == version
        )
    )
    return result.scalar_one_or_none()


async def get_skill_breakdown_for_match(session: AsyncSession, match: Match, taxonomy: SkillTaxonomy) -> SkillBreakdown:
    """Computed fresh from the match's resume/job rather than stored —
    cheap (taxonomy lookups only, no embeddings) and keeps it consistent
    for both POST /matches and GET /matches/{id} without a schema change
    to the matches table (docs/ARCHITECTURE.md §5 doesn't have a column
    for it, and it's fully derivable from data already stored)."""
    resume = await session.get(Resume, match.resume_id)
    job = await session.get(Job, match.job_id)
    candidate = CandidateProfile.model_validate(resume.parsed_profile)
    job_profile = JobProfile.model_validate(job.parsed_profile)
    return compute_skill_breakdown(candidate, job_profile, taxonomy)
