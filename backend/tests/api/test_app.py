import pytest


@pytest.mark.asyncio
async def test_health_check(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_openapi_docs_render(client) -> None:
    """Phase 8 test procedure per docs/ROADMAP.md: OpenAPI docs render at /docs."""
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


@pytest.mark.asyncio
async def test_openapi_schema_lists_all_v1_endpoints(client) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/v1/resumes",
        "/api/v1/resumes/{resume_id}",
        "/api/v1/resumes/{resume_id}/matches",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/matches",
        "/api/v1/matches/{match_id}",
        "/api/v1/skills/taxonomy",
    ):
        assert expected in paths, expected
