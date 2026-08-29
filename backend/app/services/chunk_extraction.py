"""CandidateProfile/JobProfile -> embeddable text chunks (Phase 6).

Each bullet/responsibility is its own chunk — the same "one bullet = one
evidence unit" granularity Phase 3 preserved them at, since this is what
Phase 7's per-bullet semantic-similarity features (`semantic_experience_similarity`,
`project_relevance_similarity`) and Phase 12's evidence citations both key
off of. List position becomes `chunk_index` when stored.
"""
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile


def extract_resume_experience_chunks(profile: CandidateProfile) -> list[str]:
    return [bullet for entry in profile.experience for bullet in entry.bullets]


def extract_resume_project_chunks(profile: CandidateProfile) -> list[str]:
    return [bullet for entry in profile.projects for bullet in entry.bullets]


def extract_job_responsibility_chunks(profile: JobProfile) -> list[str]:
    return list(profile.responsibilities)
