"""JD text or file -> stored Job row (Phase 8). Orchestrates Phase 1/4:
parse (pasted text or uploaded file) -> detect requirement sections ->
extract JobProfile -> persist. Unlike resumes, nothing is saved to disk —
jobs have no storage_path (app/models/job.py).
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.nlp.jd_section_detector import detect_jd_sections
from app.nlp.job_information_extraction import extract_job_profile
from app.parsers.dispatch import parse_uploaded_document
from app.parsers.text_parser import parse_text
from app.schemas.document import ParsedDocument

PARSER_VERSION = "jd-parser@0.1.0"


async def ingest_job_from_text(
    session: AsyncSession,
    raw_text: str,
    title: str | None = None,
    company: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> Job:
    return await _store_job(session, parse_text(raw_text), "pasted", title, company, owner_id)


async def ingest_job_from_file(
    session: AsyncSession,
    filename: str,
    data: bytes,
    title: str | None = None,
    company: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> Job:
    return await _store_job(session, parse_uploaded_document(filename, data), "uploaded", title, company, owner_id)


async def _store_job(
    session: AsyncSession,
    parsed: ParsedDocument,
    source: str,
    title: str | None,
    company: str | None,
    owner_id: uuid.UUID | None,
) -> Job:
    profile = extract_job_profile(detect_jd_sections(parsed))

    job = Job(
        owner_id=owner_id,
        title=title or profile.title,
        company=company,
        source=source,
        raw_text=parsed.raw_text,
        parsed_profile=profile.model_dump(mode="json"),
        parser_version=PARSER_VERSION,
    )
    session.add(job)
    await session.flush()
    return job
