"""Compute and store embeddings for every taxonomy skill (Phase 6) —
populates the `skills.embedding` column that Phase 5's stage 3 needs but
left NULL, since no embedding service existed yet.

Embeds each skill's canonical_name alone (not aliases/category) — matching
what a raw resume/JD skill mention actually looks like at query time
(app/services/skill_embedding_lookup.py embeds the raw input the same way).

Run (from backend/, with postgres up and migrations applied):
    python -m scripts.embed_skills
"""
import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models.skill import Skill
from app.services.embedding_service import get_embedding_service


async def main() -> None:
    embedding_service = get_embedding_service()
    async with SessionLocal() as session:
        result = await session.execute(select(Skill))
        skills = list(result.scalars())

        print(f"Embedding {len(skills)} skills with {embedding_service.model_name}...")
        vectors = embedding_service.embed([s.canonical_name for s in skills])
        for skill, vector in zip(skills, vectors):
            skill.embedding = vector

        await session.commit()
        print(f"Done — {len(skills)} skills now have embeddings.")


if __name__ == "__main__":
    asyncio.run(main())
