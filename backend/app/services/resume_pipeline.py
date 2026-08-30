"""Resume upload -> stored Resume row (Phase 8). Orchestrates Phases 1-3:
parse -> detect sections -> extract CandidateProfile -> persist. The
original file is saved to local disk (`storage_path`) rather than object
storage — matching the "local path" option Architecture §4 names, since
no object-storage infra exists in this project.
"""
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.resume import Resume
from app.nlp.information_extraction import extract_candidate_profile
from app.nlp.section_detector import detect_sections
from app.parsers.dispatch import detect_file_type, parse_uploaded_document

PARSER_VERSION = "resume-parser@0.1.0"


async def ingest_resume(
    session: AsyncSession, filename: str, data: bytes, owner_id: uuid.UUID | None = None
) -> Resume:
    file_type = detect_file_type(filename)
    parsed = parse_uploaded_document(filename, data)
    sectioned = detect_sections(parsed)
    profile = extract_candidate_profile(sectioned)

    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        owner_id=owner_id,
        original_filename=filename,
        file_type=file_type,
        storage_path=_save_upload(resume_id, file_type, data),
        raw_text=parsed.raw_text,
        parsed_profile=profile.model_dump(mode="json"),
        parser_version=PARSER_VERSION,
    )
    session.add(resume)
    await session.flush()
    return resume


def _save_upload(resume_id: uuid.UUID, file_type: str, data: bytes) -> str:
    upload_dir = Path(get_settings().upload_dir) / "resumes"
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{resume_id}.{file_type}"
    path.write_bytes(data)
    return str(path)
