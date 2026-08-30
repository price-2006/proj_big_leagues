"""(resume, job) -> stored Match row (Phase 8). Orchestrates Phases 5-7:
skill taxonomy + embeddings -> the 10-feature vector -> rule-based score
-> persist. Idempotent within a scoring_model_version: computing the same
pair twice returns the existing row rather than recomputing (the
embedding calls aren't free, and the result would be identical anyway
since it's a pure function of the stored profiles + weights).
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_engineering import compute_feature_vector
from app.ml.rule_based_scorer import score
from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile
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

    existing = await session.execute(
        select(Match).where(
            Match.resume_id == resume_id, Match.job_id == job_id, Match.scoring_model_version == version
        )
    )
    existing_match = existing.scalar_one_or_none()
    if existing_match is not None:
        return existing_match

    candidate = CandidateProfile.model_validate(resume.parsed_profile)
    job_profile = JobProfile.model_validate(job.parsed_profile)
    features = compute_feature_vector(candidate, job_profile, taxonomy, embedding_service, as_of=date.today())
    rule_based_score = score(features, weights)

    match = Match(
        resume_id=resume_id,
        job_id=job_id,
        feature_vector=features.model_dump(mode="json"),
        rule_based_score=Decimal(str(round(rule_based_score * 100, 2))),
        scoring_model_version=version,
    )
    session.add(match)
    await session.flush()
    return match
