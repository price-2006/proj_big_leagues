"""Wires a real embedding_lookup into Phase 5's normalize_skill() —
the seam app/services/skill_normalization_service.py left open pending
this phase, filled without changing a line of Phase 5's code.

The taxonomy is small (~200 skills), so this loads every skill's
embedding into memory once and does a plain linear cosine scan per
lookup rather than an async pgvector query per call — simpler, and fast
enough at this scale. pgvector's ivfflat index (Phase 6, text_embeddings)
earns its keep at resume/job scale, not here.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.services.embedding_service import EmbeddingService, cosine_similarity
from app.services.skill_normalization_service import SkillTaxonomy


async def load_skill_embeddings(session: AsyncSession) -> list[tuple[str, list[float]]]:
    result = await session.execute(select(Skill.canonical_name, Skill.embedding).where(Skill.embedding.isnot(None)))
    return [(name, list(embedding)) for name, embedding in result.all()]


def build_embedding_lookup(skill_embeddings: list[tuple[str, list[float]]], embedding_service: EmbeddingService):
    """Returns a sync callable matching Phase 5's EmbeddingCandidateLookup
    signature: (raw_text, taxonomy, top_k) -> [(canonical_name, similarity), ...]."""

    def lookup(raw_text: str, taxonomy: SkillTaxonomy, top_k: int) -> list[tuple[str, float]]:
        [query_vector] = embedding_service.embed([raw_text])
        scored = [(name, cosine_similarity(query_vector, vector)) for name, vector in skill_embeddings]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    return lookup
