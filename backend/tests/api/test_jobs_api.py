"""JD ingestion needs no spaCy (Phase 4 never uses it), so this is the one
full parse-through-API flow verifiable in this environment right now —
see tests/api/test_resumes_api.py for why the resume path is xfailed.
"""
import pytest

JD_TEXT = """Senior Data Engineer

Requirements
- 5+ years of experience in data engineering
- Strong proficiency in Python and SQL

Preferred Qualifications
- Experience with Kafka

Responsibilities
- Design and maintain large-scale data pipelines
"""


@pytest.mark.asyncio
async def test_create_job_from_pasted_text_and_fetch_it(client) -> None:
    create_response = await client.post("/api/v1/jobs", data={"raw_text": JD_TEXT})
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["title"] == "Senior Data Engineer"
    assert body["source"] == "pasted"
    assert body["parsed_profile"]["seniority"] == "senior"
    required = [r for r in body["parsed_profile"]["requirements"] if r["level"] == "required"]
    assert any("Python" in r["skills"] for r in required)

    fetch_response = await client.get(f"/api/v1/jobs/{body['id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json() == body


@pytest.mark.asyncio
async def test_create_job_requires_exactly_one_of_text_or_file(client) -> None:
    neither = await client.post("/api/v1/jobs", data={})
    assert neither.status_code == 400
    assert neither.json()["error"]["code"] == "400"


@pytest.mark.asyncio
async def test_create_job_rejects_both_text_and_file(client) -> None:
    response = await client.post(
        "/api/v1/jobs", data={"raw_text": JD_TEXT}, files={"file": ("x.pdf", b"not a real pdf", "application/pdf")}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_nonexistent_job_returns_404_with_consistent_error_shape(client) -> None:
    response = await client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "404"
    assert "not found" in body["error"]["message"].lower()
