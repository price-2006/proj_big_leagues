from app.schemas.candidate_profile import CandidateProfile, ExperienceEntry, ProjectEntry
from app.schemas.job_profile import JobProfile
from app.services.chunk_extraction import (
    extract_job_responsibility_chunks,
    extract_resume_experience_chunks,
    extract_resume_project_chunks,
)


def test_extract_resume_experience_chunks_flattens_bullets_across_entries():
    profile = CandidateProfile(
        contact={},
        experience=[
            ExperienceEntry(title="A", bullets=["bullet 1", "bullet 2"]),
            ExperienceEntry(title="B", bullets=["bullet 3"]),
        ],
    )
    assert extract_resume_experience_chunks(profile) == ["bullet 1", "bullet 2", "bullet 3"]


def test_extract_resume_project_chunks_flattens_bullets_across_entries():
    profile = CandidateProfile(
        contact={},
        projects=[ProjectEntry(name="X", bullets=["did a thing"]), ProjectEntry(name="Y", bullets=[])],
    )
    assert extract_resume_project_chunks(profile) == ["did a thing"]


def test_extract_job_responsibility_chunks_returns_them_as_is():
    profile = JobProfile(responsibilities=["Own the roadmap", "Ship features"])
    assert extract_job_responsibility_chunks(profile) == ["Own the roadmap", "Ship features"]


def test_extract_chunks_empty_when_no_bullets():
    profile = CandidateProfile(contact={})
    assert extract_resume_experience_chunks(profile) == []
    assert extract_resume_project_chunks(profile) == []
