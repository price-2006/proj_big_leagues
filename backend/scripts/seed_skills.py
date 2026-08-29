"""Seed skills / skill_aliases / skill_disambiguation_rules (Phase 5).

Idempotent — re-running skips rows that already exist (on_conflict_do_nothing
against the unique constraints on canonical_name / alias / the disambiguation
pair), so it's safe to run again after adding new entries to
app/services/skill_seed_data.py.

Run (from backend/, with postgres up and `alembic upgrade head` applied):
    python -m scripts.seed_skills
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.skill import Skill, SkillAlias, SkillDisambiguationRule
from app.services.onet_loader import fetch_onet_software_skills_csv, onet_category_to_internal, parse_hot_technologies
from app.services.skill_seed_data import INTERNAL_DISAMBIGUATION_PAIRS, INTERNAL_SKILLS


async def seed(session: AsyncSession) -> None:
    skills_added = aliases_added = 0

    for seed_skill in INTERNAL_SKILLS:
        skills_added += await _upsert_skill(session, seed_skill.canonical_name, seed_skill.category, "internal")
        for alias in seed_skill.aliases:
            aliases_added += await _upsert_alias(session, seed_skill.canonical_name, alias)

    print("Fetching O*NET Software Skills (Hot Technology only)...")
    csv_text = fetch_onet_software_skills_csv()
    onet_skills = parse_hot_technologies(csv_text)
    print(f"  {len(onet_skills)} Hot-Technology entries found")
    for canonical_name, element_name in onet_skills:
        skills_added += await _upsert_skill(session, canonical_name, onet_category_to_internal(element_name), "onet")

    rules_added = 0
    for skill_a, skill_b, reason in INTERNAL_DISAMBIGUATION_PAIRS:
        rules_added += await _upsert_disambiguation_rule(session, skill_a, skill_b, reason)

    await session.commit()
    print(f"Seeded: {skills_added} skills, {aliases_added} aliases, {rules_added} disambiguation rules")


async def _upsert_skill(session: AsyncSession, canonical_name: str, category: str, source: str) -> int:
    stmt = (
        pg_insert(Skill)
        .values(canonical_name=canonical_name, category=category, source=source)
        .on_conflict_do_nothing(index_elements=["canonical_name"])
        .returning(Skill.id)
    )
    result = await session.execute(stmt)
    return 1 if result.first() is not None else 0


async def _upsert_alias(session: AsyncSession, canonical_name: str, alias: str) -> int:
    skill_id = await _get_skill_id(session, canonical_name)
    if skill_id is None:
        return 0
    stmt = (
        pg_insert(SkillAlias)
        .values(skill_id=skill_id, alias=alias)
        .on_conflict_do_nothing(index_elements=["alias"])
        .returning(SkillAlias.id)
    )
    result = await session.execute(stmt)
    return 1 if result.first() is not None else 0


async def _upsert_disambiguation_rule(session: AsyncSession, skill_a_name: str, skill_b_name: str, reason: str) -> int:
    skill_a_id = await _get_skill_id(session, skill_a_name)
    skill_b_id = await _get_skill_id(session, skill_b_name)
    if skill_a_id is None or skill_b_id is None:
        print(f"  skipping disambiguation rule ({skill_a_name}, {skill_b_name}): skill not seeded")
        return 0
    stmt = (
        pg_insert(SkillDisambiguationRule)
        .values(skill_a_id=skill_a_id, skill_b_id=skill_b_id, reason=reason)
        .on_conflict_do_nothing(index_elements=["skill_a_id", "skill_b_id"])
        .returning(SkillDisambiguationRule.id)
    )
    result = await session.execute(stmt)
    return 1 if result.first() is not None else 0


async def _get_skill_id(session: AsyncSession, canonical_name: str):
    result = await session.execute(select(Skill.id).where(Skill.canonical_name == canonical_name))
    row = result.first()
    return row[0] if row else None


async def main() -> None:
    async with SessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
