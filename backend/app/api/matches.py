"""POST /matches, GET /matches/{id} (Phase 8, docs/ARCHITECTURE.md §10).
Returns the Match (score + full feature breakdown) — no explanation
field. `match_explanations` is Phase 12's LLM layer; it isn't built yet,
so this deliberately doesn't fake one.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_taxonomy
from app.db import get_session
from app.models.match import Match
from app.schemas.match_api import MatchCreateRequest, MatchResponse
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.match_pipeline import JobNotFoundError, ResumeNotFoundError, compute_and_store_match
from app.services.skill_normalization_service import SkillTaxonomy

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchResponse, status_code=201)
async def create_match(
    body: MatchCreateRequest,
    session: AsyncSession = Depends(get_session),
    taxonomy: SkillTaxonomy = Depends(get_taxonomy),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> Match:
    try:
        match = await compute_and_store_match(session, body.resume_id, body.job_id, taxonomy, embedding_service)
    except ResumeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Resume {body.resume_id} not found") from exc
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Job {body.job_id} not found") from exc

    await session.commit()
    await session.refresh(match)
    return match


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(match_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Match:
    match = await session.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return match
