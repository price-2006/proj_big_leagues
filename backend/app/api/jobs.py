"""POST /jobs, GET /jobs/{id} (Phase 8, docs/ARCHITECTURE.md §10). One
multipart-form endpoint accepts either pasted text or an uploaded file —
matching the API design's stated "pasted text or an uploaded file" — not
both, and not neither.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.job import Job
from app.parsers.exceptions import DocumentParseError
from app.schemas.job_api import JobResponse
from app.services.job_pipeline import ingest_job_from_file, ingest_job_from_text

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    raw_text: str | None = Form(None),
    title: str | None = Form(None),
    company: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> Job:
    if bool(raw_text) == bool(file):
        raise HTTPException(status_code=400, detail="Provide exactly one of `raw_text` or `file`")

    try:
        if raw_text:
            job = await ingest_job_from_text(session, raw_text, title=title, company=company)
        else:
            data = await file.read()
            job = await ingest_job_from_file(session, file.filename, data, title=title, company=company)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job
