"""Loads the full skill taxonomy from Postgres into the in-memory
SkillTaxonomy shape the normalization service (Phase 5) expects. Loaded
once at app startup (Phase 8's lifespan) and cached — the taxonomy is
small (~200 skills) and doesn't change mid-request.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillAlias, SkillDisambiguationRule
from app.services.skill_normalization_service import DisambiguationPair, SkillTaxonomy, TaxonomySkill


async def load_taxonomy_from_db(session: AsyncSession) -> SkillTaxonomy:
    skill_rows = list((await session.execute(select(Skill))).scalars())
    id_to_name = {s.id: s.canonical_name for s in skill_rows}

    aliases_by_skill_id: dict = {}
    for alias in (await session.execute(select(SkillAlias))).scalars():
        aliases_by_skill_id.setdefault(alias.skill_id, []).append(alias.alias)

    skills = [
        TaxonomySkill(s.canonical_name, s.category, aliases_by_skill_id.get(s.id, [])) for s in skill_rows
    ]

    pairs = [
        DisambiguationPair(id_to_name[r.skill_a_id], id_to_name[r.skill_b_id], r.reason)
        for r in (await session.execute(select(SkillDisambiguationRule))).scalars()
        if r.skill_a_id in id_to_name and r.skill_b_id in id_to_name
    ]

    return SkillTaxonomy(skills, pairs)
