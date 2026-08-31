"""Test DB + httpx client fixtures for the API integration suite (Phase 8).

Uses a separate `resume_matcher_test` database (created if missing),
schema built via Base.metadata.create_all() rather than replaying Alembic
migrations — faster, and it's the schema that matters for these tests,
not migration history. `get_taxonomy` is overridden to build the
SkillTaxonomy in-memory from the same seed data scripts/seed_skills.py
uses (app/services/skill_seed_data.py), so tests don't depend on the
skills table being seeded in the test DB.
"""
import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_taxonomy
from app.config import get_settings
from app.db import Base, get_session
from app.main import app
from app.models import job, match, match_explanation, resume, scoring_weights, skill, text_embedding  # noqa: F401 — completes Base.metadata
from app.services.skill_normalization_service import DisambiguationPair, SkillTaxonomy, TaxonomySkill
from app.services.skill_seed_data import INTERNAL_DISAMBIGUATION_PAIRS, INTERNAL_SKILLS

TEST_DB_NAME = "resume_matcher_test"

# Derived from the configured DATABASE_URL (host/user/password/port),
# swapping only the database name — not hardcoded to localhost, since
# that resolves differently running locally vs. inside the backend
# container (where postgres is reachable at hostname "postgres", per
# docker-compose.yml).
_configured_url = get_settings().database_url
_base_url, _, _ = _configured_url.rpartition("/")
ADMIN_DSN = f"{_base_url}/resume_matcher".replace("postgresql+asyncpg://", "postgresql://")
TEST_DATABASE_URL = f"{_base_url}/{TEST_DB_NAME}"


async def _ensure_test_database_exists() -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    await _ensure_test_database_exists()
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """A session tests can use to seed rows directly, bypassing the API —
    e.g. inserting a Resume with a hand-built parsed_profile where the
    real extraction pipeline can't run (see tests/api/test_matches_api.py)."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


def _in_memory_taxonomy() -> SkillTaxonomy:
    skills = [TaxonomySkill(s.canonical_name, s.category, s.aliases) for s in INTERNAL_SKILLS]
    pairs = [DisambiguationPair(a, b, r) for a, b, r in INTERNAL_DISAMBIGUATION_PAIRS]
    return SkillTaxonomy(skills, pairs)


@pytest_asyncio.fixture
async def client(test_engine, db_session):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_taxonomy] = _in_memory_taxonomy

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
