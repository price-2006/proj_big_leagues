"""POST /resumes, GET /resumes/{id}, GET /resumes/{resume_id}/matches,
POST /resumes/{resume_id}/recommendations (Phases 8 and 12,
docs/ARCHITECTURE.md §10)."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_taxonomy
from app.db import get_session
from app.models.match import Match
from app.models.resume import Resume
from app.parsers.exceptions import DocumentParseError
from app.schemas.match_api import MatchResponse, build_match_response
from app.schemas.match_explanation_api import MatchExplanationResponse, build_match_explanation_response
from app.schemas.resume_api import ResumeResponse
from app.services.explanation_service import get_or_generate_explanation
from app.services.llm_service import LLMGenerationError, LLMService, get_llm_service
from app.services.match_pipeline import find_match_by_resume_and_job, get_skill_breakdown_for_match
from app.services.resume_pipeline import ingest_resume
from app.services.skill_normalization_service import SkillTaxonomy

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeResponse, status_code=201)
async def upload_resume(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)) -> Resume:
    data = await file.read()
    try:
        resume = await ingest_resume(session, file.filename, data)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Resume:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    return resume


@router.get("/{resume_id}/matches", response_model=list[MatchResponse])
async def list_resume_matches(
    resume_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    taxonomy: SkillTaxonomy = Depends(get_taxonomy),
) -> list[MatchResponse]:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    result = await session.execute(
        select(Match).where(Match.resume_id == resume_id).order_by(Match.rule_based_score.desc())
    )
    matches = list(result.scalars())
    return [build_match_response(m, await get_skill_breakdown_for_match(session, m, taxonomy)) for m in matches]


@router.post("/{resume_id}/recommendations", response_model=MatchExplanationResponse, status_code=201)
async def get_recommendations(
    resume_id: uuid.UUID,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    taxonomy: SkillTaxonomy = Depends(get_taxonomy),
    llm_service: LLMService = Depends(get_llm_service),
) -> MatchExplanationResponse:
    """Phase 12. Requires an already-computed Match for (resume_id,
    job_id) — POST /matches first — never scores on the fly here, so the
    score is always already committed before any LLM call happens."""
    match = await find_match_by_resume_and_job(session, resume_id, job_id)
    if match is None:
        raise HTTPException(
            status_code=404, detail=f"No match found for resume {resume_id} and job {job_id} — POST /matches first"
        )
    try:
        row, _ = await get_or_generate_explanation(session, match, taxonomy, llm_service)
    except LLMGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    return build_match_explanation_response(row)
