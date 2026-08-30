"""GET /skills/taxonomy queries the DB directly (not the in-memory
SkillTaxonomy the `client` fixture injects for matching), so this seeds
a row into the test DB itself to verify the endpoint's own query/response
logic — a real 194-skill taxonomy exists only once scripts/seed_skills.py
has run against a real database (verified manually, see docs/ROADMAP.md
Phase 5's write-up).
"""
import pytest

from app.models.skill import Skill, SkillAlias


@pytest.mark.asyncio
async def test_browse_taxonomy_returns_seeded_skills_with_aliases(client, db_session) -> None:
    skill = Skill(canonical_name="Python", category="programming_language", source="internal")
    db_session.add(skill)
    await db_session.flush()
    db_session.add(SkillAlias(skill_id=skill.id, alias="python3"))
    await db_session.commit()

    response = await client.get("/api/v1/skills/taxonomy")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["skills"][0]["canonical_name"] == "Python"
    assert body["skills"][0]["source"] == "internal"
    assert "python3" in body["skills"][0]["aliases"]


@pytest.mark.asyncio
async def test_browse_taxonomy_empty_when_no_skills_seeded(client) -> None:
    response = await client.get("/api/v1/skills/taxonomy")
    assert response.status_code == 200
    assert response.json() == {"skills": [], "total": 0}
