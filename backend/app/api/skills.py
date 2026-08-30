"""GET /skills/taxonomy (Phase 8, docs/ARCHITECTURE.md §10) — browse the
normalized skill taxonomy. Debugging/admin use, per Architecture; no
pagination since ~200 rows is small enough to return whole.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.skill import Skill, SkillAlias
from app.schemas.skill_api import SkillTaxonomyEntry, SkillTaxonomyResponse

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/taxonomy", response_model=SkillTaxonomyResponse)
async def browse_taxonomy(session: AsyncSession = Depends(get_session)) -> SkillTaxonomyResponse:
    skills = list((await session.execute(select(Skill).order_by(Skill.canonical_name))).scalars())

    aliases_by_skill_id: dict = {}
    for alias in (await session.execute(select(SkillAlias))).scalars():
        aliases_by_skill_id.setdefault(alias.skill_id, []).append(alias.alias)

    entries = [
        SkillTaxonomyEntry(
            canonical_name=s.canonical_name,
            category=s.category,
            source=s.source,
            aliases=aliases_by_skill_id.get(s.id, []),
        )
        for s in skills
    ]
    return SkillTaxonomyResponse(skills=entries, total=len(entries))
