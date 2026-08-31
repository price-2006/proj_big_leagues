"""Phase 12 test procedure per docs/ROADMAP.md: adversarial cases assert
the validator strips/rejects unfounded claims and the score is provably
unaffected by LLM output (score computed and stored before the LLM call
happens). This exercises that end-to-end against a real DB: create a
match (score computed + committed), fetch it, call the recommendations
endpoint with a fake/adversarial LLM response, then re-fetch the match
and assert its score is byte-identical — nothing in the explanation path
could have touched it.
"""
import pytest

from app.api.dependencies import get_taxonomy
from app.main import app
from app.models.resume import Resume
from app.schemas.match_explanation import EvidencedClaim, MatchExplanation, Recommendation
from app.services.llm_service import LLMGenerationError, get_llm_service

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
        {"degree": "B.S.", "field_of_study": "Computer Science", "institution": "State University", "graduation_year": "2015"}
    ],
    "certifications": [],
}

JD_TEXT = (
    "Senior Backend Engineer\n\n"
    "Requirements\n"
    "- Strong experience with Python and PostgreSQL\n"
    "- Experience with Rust\n\n"
    "Responsibilities\n"
    "- Design and build scalable backend APIs\n"
)


class FakeLLMService:
    model_name = "fake-model"

    def __init__(self, response: MatchExplanation | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.call_count = 0

    async def generate_structured(self, prompt, response_schema):
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return self._response


async def _seed_resume(db_session) -> str:
    resume = Resume(
        original_filename="alex.pdf",
        file_type="pdf",
        storage_path="test-fixture",
        raw_text="test fixture — bypasses the real parser",
        parsed_profile=STRONG_CANDIDATE_PROFILE,
        parser_version="test-fixture",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return str(resume.id)


async def _create_match(client, resume_id: str) -> dict:
    job_response = await client.post("/api/v1/jobs", data={"raw_text": JD_TEXT})
    job_id = job_response.json()["id"]
    match_response = await client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id})
    assert match_response.status_code == 201
    return match_response.json()


def _valid_fake_explanation() -> MatchExplanation:
    return MatchExplanation(
        narrative="Strong alignment on core backend skills.",
        strengths=[
            EvidencedClaim(
                text="Designed and built scalable backend APIs serving millions of requests",
                evidence_ref="experience[0].bullets[0]",
                is_inference=False,
            )
        ],
        weaknesses=[EvidencedClaim(text="No direct Rust experience listed", evidence_ref=None, is_inference=True)],
        missing_skills=["Rust"],
        recommendations=[
            Recommendation(suggestion="Highlight the PostgreSQL optimization work", based_on="experience[0].bullets[1]")
        ],
    )


@pytest.mark.asyncio
async def test_recommendations_requires_an_existing_match(client, db_session):
    resume_id = await _seed_resume(db_session)
    job_response = await client.post("/api/v1/jobs", data={"raw_text": JD_TEXT})
    job_id = job_response.json()["id"]

    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(response=_valid_fake_explanation())
    response = await client.post(f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": job_id})
    assert response.status_code == 404
    assert "match" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_recommendations_generates_and_persists_a_validated_explanation(client, db_session):
    resume_id = await _seed_resume(db_session)
    match = await _create_match(client, resume_id)
    score_before = match["rule_based_score"]

    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(response=_valid_fake_explanation())
    response = await client.post(
        f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": match["job_id"]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["match_id"] == match["id"]
    assert body["evidence_check_passed"] is True
    assert len(body["strengths"]) == 1
    assert body["missing_skills"] == ["Rust"]
    assert body["llm_model"] == "fake-model"

    refetched = await client.get(f"/api/v1/matches/{match['id']}")
    assert refetched.json()["rule_based_score"] == score_before  # untouched by the explanation call


@pytest.mark.asyncio
async def test_recommendations_is_idempotent_and_does_not_recall_the_llm(client, db_session):
    resume_id = await _seed_resume(db_session)
    match = await _create_match(client, resume_id)

    fake = FakeLLMService(response=_valid_fake_explanation())
    app.dependency_overrides[get_llm_service] = lambda: fake

    first = await client.post(f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": match["job_id"]})
    second = await client.post(f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": match["job_id"]})

    assert first.json()["id"] == second.json()["id"]
    assert fake.call_count == 1  # the second request reused the stored row, no second LLM call


@pytest.mark.asyncio
async def test_recommendations_strips_unfounded_claims_from_a_compromised_llm_response(client, db_session):
    """Simulates a resume containing prompt-injection text that "worked":
    the fake LLM returns a claim citing an evidence_ref that doesn't
    exist on this candidate's real profile. The persisted explanation
    must not contain it."""
    resume_id = await _seed_resume(db_session)
    match = await _create_match(client, resume_id)

    compromised = MatchExplanation(
        narrative="Perfect match, no weaknesses.",
        strengths=[
            EvidencedClaim(text="10 years of Rust expertise", evidence_ref="experience[9].bullets[9]", is_inference=False)
        ],
        weaknesses=[],
        missing_skills=["Rust", "Quantum Computing"],  # "Quantum Computing" was never actually computed as missing
        recommendations=[],
    )
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(response=compromised)
    response = await client.post(f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": match["job_id"]})

    assert response.status_code == 201
    body = response.json()
    assert body["strengths"] == []  # the fabricated evidence_ref didn't resolve
    assert body["missing_skills"] == ["Rust"]  # "Quantum Computing" was dropped
    assert body["evidence_check_passed"] is False

    refetched = await client.get(f"/api/v1/matches/{match['id']}")
    assert refetched.json()["rule_based_score"] == match["rule_based_score"]


@pytest.mark.asyncio
async def test_recommendations_returns_502_when_the_llm_provider_fails(client, db_session):
    resume_id = await _seed_resume(db_session)
    match = await _create_match(client, resume_id)

    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(error=LLMGenerationError("boom"))
    response = await client.post(f"/api/v1/resumes/{resume_id}/recommendations", params={"job_id": match["job_id"]})

    assert response.status_code == 502
