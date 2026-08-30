"""POST /resumes, GET /resumes/{id}, GET /resumes/{resume_id}/matches
(Phase 8, docs/ARCHITECTURE.md §10)."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.match import Match
from app.models.resume import Resume
from app.parsers.exceptions import DocumentParseError
from app.schemas.match_api import MatchResponse
from app.schemas.resume_api import ResumeResponse
from app.services.resume_pipeline import ingest_resume

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
async def list_resume_matches(resume_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[Match]:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    result = await session.execute(
        select(Match).where(Match.resume_id == resume_id).order_by(Match.rule_based_score.desc())
    )
    return list(result.scalars())
