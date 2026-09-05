"""POST /jobs, GET /jobs/{id} (Phase 8, docs/ARCHITECTURE.md §10). One
multipart-form endpoint accepts either pasted text or an uploaded file —
matching the API design's stated "pasted text or an uploaded file" — not
both, and not neither.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.job import Job
from app.parsers.dispatch import detect_file_type
from app.parsers.exceptions import DocumentParseError
from app.rate_limiter import limiter
from app.schemas.job_api import JobResponse
from app.services.job_pipeline import ingest_job_from_file, ingest_job_from_text
from app.services.upload_validation import (
    UnrecognizedFileSignatureError,
    UploadTooLargeError,
    read_upload_within_limit,
    verify_magic_bytes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
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
            file_type = detect_file_type(file.filename)
            data = await read_upload_within_limit(file)
            verify_magic_bytes(data, file_type)
            job = await ingest_job_from_file(session, file.filename, data, title=title, company=company)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnrecognizedFileSignatureError as exc:
        logger.warning("job upload rejected: reason=magic_byte_mismatch file_type=%s", exc.file_type)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        logger.warning("job upload rejected: reason=too_large max_bytes=%s", exc.max_bytes)
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job
