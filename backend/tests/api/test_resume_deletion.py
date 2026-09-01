"""Phase 14, docs/ARCHITECTURE.md §12: "a delete endpoint (DELETE
/resumes/{id}) purges the row and its embeddings/matches." Resume seeded
directly into the test DB (bypassing spaCy) — same reasoning as
tests/api/test_matches_api.py's _seed_resume: these tests are about
deletion/cleanup, not extraction.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.match import Match
from app.models.resume import Resume
from app.models.text_embedding import TextEmbedding
from app.models.training_label import TrainingLabel

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
            "bullets": ["Designed and built scalable backend APIs serving millions of requests"],
        }
    ],
    "projects": [],
    "education": [],
    "certifications": [],
}

JD_TEXT = "Senior Backend Engineer\n\nRequirements\n- Strong experience with Python and PostgreSQL\n"


async def _seed_resume(db_session, storage_path: str) -> str:
    resume = Resume(
        original_filename="alex.pdf",
        file_type="pdf",
        storage_path=storage_path,
        raw_text="test fixture — bypasses the real parser",
        parsed_profile=STRONG_CANDIDATE_PROFILE,
        parser_version="test-fixture",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return str(resume.id)


@pytest.mark.asyncio
async def test_delete_removes_the_resume_row(client, db_session, tmp_path):
    resume_id = await _seed_resume(db_session, str(tmp_path / "resume.pdf"))

    response = await client.delete(f"/api/v1/resumes/{resume_id}")
    assert response.status_code == 204

    fetch = await client.get(f"/api/v1/resumes/{resume_id}")
    assert fetch.status_code == 404


@pytest.mark.asyncio
async def test_delete_removes_the_uploaded_file_from_disk(client, db_session, tmp_path):
    file_path = tmp_path / "resume.pdf"
    file_path.write_bytes(b"fake pdf content")
    resume_id = await _seed_resume(db_session, str(file_path))
    assert file_path.exists()

    response = await client.delete(f"/api/v1/resumes/{resume_id}")

    assert response.status_code == 204
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_delete_does_not_crash_when_the_file_is_already_missing(client, db_session, tmp_path):
    resume_id = await _seed_resume(db_session, str(tmp_path / "already_gone.pdf"))  # never created

    response = await client.delete(f"/api/v1/resumes/{resume_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_cascades_to_matches_and_text_embeddings(client, db_session, tmp_path):
    resume_id = await _seed_resume(db_session, str(tmp_path / "resume.pdf"))

    job_response = await client.post("/api/v1/jobs", data={"raw_text": JD_TEXT})
    job_id = job_response.json()["id"]
    match_response = await client.post("/api/v1/matches", json={"resume_id": resume_id, "job_id": job_id})
    match_id = match_response.json()["id"]

    db_session.add(
        TextEmbedding(
            entity_type="resume_experience",
            entity_id=uuid.UUID(resume_id),
            chunk_index=0,
            chunk_text="irrelevant",
            embedding_model="test",
            embedding=[0.0] * 384,
        )
    )
    await db_session.commit()

    response = await client.delete(f"/api/v1/resumes/{resume_id}")
    assert response.status_code == 204

    remaining_match = (await db_session.execute(select(Match).where(Match.id == uuid.UUID(match_id)))).scalar_one_or_none()
    assert remaining_match is None

    remaining_embedding = (
        await db_session.execute(select(TextEmbedding).where(TextEmbedding.entity_id == uuid.UUID(resume_id)))
    ).scalar_one_or_none()
    assert remaining_embedding is None


@pytest.mark.asyncio
async def test_delete_nulls_out_referencing_training_labels_instead_of_leaving_a_dangling_fk(client, db_session, tmp_path):
    resume_id = await _seed_resume(db_session, str(tmp_path / "resume.pdf"))
    db_session.add(
        TrainingLabel(resume_id=uuid.UUID(resume_id), label=0.8, label_source="test", dataset_split="train")
    )
    await db_session.commit()

    response = await client.delete(f"/api/v1/resumes/{resume_id}")
    assert response.status_code == 204

    row = (await db_session.execute(select(TrainingLabel).where(TrainingLabel.label_source == "test"))).scalar_one()
    assert row.resume_id is None  # row survives — real training data isn't disposable — just un-referenced


@pytest.mark.asyncio
async def test_delete_nonexistent_resume_returns_404(client):
    response = await client.delete("/api/v1/resumes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
