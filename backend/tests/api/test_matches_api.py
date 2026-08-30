"""Phase 8 test procedure per docs/ROADMAP.md: an integration test suite
exercising upload -> parse -> match -> fetch, asserting response schemas
and non-trivial score output.

The resume side of "upload" is seeded directly into the test DB with a
hand-built CandidateProfile (exactly the shape Phase 3's extractor would
have produced) rather than going through POST /resumes, since resume
extraction needs spaCy, currently blocked in this environment — see
tests/api/test_resumes_api.py. This still exercises the real thing this
phase is actually about: feature engineering (Phase 7) + scoring, running
for real through the live API, DB, and embedding model — matching the
strong-candidate fixture already verified in Phase 7's own tests.
"""
import asyncio

import pytest

from app.models.resume import Resume

STRONG_CANDIDATE_PROFILE = {
    "contact": {"name": "Alex Kim", "email": None, "phone": None, "location": None, "links": []},
    "summary": "Backend engineer specializing in fintech payment systems",
    "skills": ["Python", "PostgreSQL", "Docker", "Kubernetes"],
    "experience": [
        {
            "title": "Senior Backend Engineer",
            "organization": "PayCo",
            "start_date": "Jan 2019",
            "end_date": "Present",
            "bullets": [
                "Designed and built scalable backend APIs serving millions of requests",
                "Optimized PostgreSQL database performance",
            ],
        }
    ],
    "projects": [],
    "education": [
        {
            "degree": "B.S.",
            "field_of_study": "Computer Science",
            "institution": "State University",
            "graduation_year": "2015",
        }
    ],
    "certifications": [],
}

JD_TEXT = (
    "Senior Backend Engineer\n\n"
    "Requirements\n"
    "- Strong experience with Python and PostgreSQL\n\n"
    "Responsibilities\n"
    "- Design and build scalable backend APIs\n"
)


async def _seed_resume(db_session) -> str:
    resume = Resume(
        original_filename="alex.pdf",
        file_type="pdf",
        storage_path="test-fixture",
        raw_text="test fixture — bypasses the real parser, see module docstring",
        parsed_profile=STRONG_CANDIDATE_PROFILE,
        parser_version="test-fixture",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return str(resume.id)


@pytest.mark.asyncio
async def test_full_flow_seed_resume_create_job_compute_match_and_fetch(client, db_session) -> None:
    resume_id = await _seed_resume(db_session)

    job_response = await client.post("/api/v1/jobs", data={"raw_text": JD_TEXT})
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    match_response = await client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id})
    assert match_response.status_code == 201
    match = match_response.json()

    assert match["resume_id"] == resume_id
    assert match["job_id"] == job_id
    assert match["scoring_model_version"] == "v1"
    assert match["ml_score"] is None  # Phase 11 territory, not yet computed

    # Non-trivial score: a strong, well-aligned pair should score well above zero.
    assert match["rule_based_score"] > 50
    assert match["feature_vector"]["required_skill_coverage"] == 1.0

    # Named skill breakdown (Phase 9): the JD's only required skills are
    # Python and PostgreSQL, both of which the seeded candidate has.
    assert sorted(match["skill_breakdown"]["matched_required"]) == ["PostgreSQL", "Python"]
    assert match["skill_breakdown"]["missing_required"] == []

    fetch_response = await client.get(f"/api/v1/matches/{match['id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json() == match

    resume_matches_response = await client.get(f"/api/v1/resumes/{resume_id}/matches")
    assert resume_matches_response.status_code == 200
    listed = resume_matches_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == match["id"]


@pytest.mark.asyncio
async def test_match_is_idempotent_for_the_same_scoring_version(client, db_session) -> None:
    resume_id = await _seed_resume(db_session)
    job_response = await client.post("/api/v1/jobs", data={"raw_text": "Some Role\n\nRequirements\n- Python"})
    job_id = job_response.json()["id"]

    first = await client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id})
    second = await client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_concurrent_identical_match_requests_dont_race(client, db_session) -> None:
    """Regression test for a real bug caught by actually running the
    frontend: React StrictMode double-invokes effects in dev mode, which
    fired two concurrent POST /matches for the same pair and crashed the
    second with a UniqueViolationError, because the original
    check-then-insert wasn't atomic. Fired with asyncio.gather so both
    requests are genuinely in flight at once, not sequential."""
    resume_id = await _seed_resume(db_session)
    job_response = await client.post("/api/v1/jobs", data={"raw_text": "Some Role\n\nRequirements\n- Python"})
    job_id = job_response.json()["id"]

    responses = await asyncio.gather(
        client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id}),
        client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id}),
    )
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]

    listed = await client.get(f"/api/v1/resumes/{resume_id}/matches")
    assert len(listed.json()) == 1  # exactly one row, not two


@pytest.mark.asyncio
async def test_match_with_nonexistent_resume_returns_404(client) -> None:
    job_response = await client.post("/api/v1/jobs", data={"raw_text": "Some Role\n\nRequirements\n- Python"})
    job_id = job_response.json()["id"]

    response = await client.post(
        "/api/v1/matches", json={"resume_id": "00000000-0000-0000-0000-000000000000", "job_id": job_id}
    )
    assert response.status_code == 404
    assert "Resume" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_match_with_nonexistent_job_returns_404(client, db_session) -> None:
    resume_id = await _seed_resume(db_session)
    response = await client.post(
        "/api/v1/matches", json={"resume_id": resume_id, "job_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404
    assert "Job" in response.json()["error"]["message"]
