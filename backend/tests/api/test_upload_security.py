"""Phase 14 test procedure per docs/ROADMAP.md: "a security-focused test
suite — oversized file rejected, wrong-magic-byte file rejected, XXE
payload DOCX doesn't leak file contents" — exercised through the real
POST /resumes and POST /jobs endpoints, not just the underlying unit
functions (tests/services/test_upload_validation.py,
tests/parsers/test_docx_parser.py cover those directly).
"""
from pathlib import Path

import pytest

from app.services.upload_validation import MAX_UPLOAD_SIZE_BYTES

SECURITY_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "security"


@pytest.mark.asyncio
async def test_oversized_resume_upload_is_rejected(client):
    oversized = b"%PDF-1.4 " + b"0" * MAX_UPLOAD_SIZE_BYTES  # over the cap by construction

    response = await client.post("/api/v1/resumes", files={"file": ("big.pdf", oversized, "application/pdf")})

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "413"


@pytest.mark.asyncio
async def test_oversized_job_file_upload_is_rejected(client):
    oversized = b"%PDF-1.4 " + b"0" * MAX_UPLOAD_SIZE_BYTES

    response = await client.post("/api/v1/jobs", files={"file": ("big.pdf", oversized, "application/pdf")})

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_wrong_magic_bytes_resume_upload_is_rejected(client):
    data = (SECURITY_FIXTURES / "wrong_magic_bytes.pdf").read_bytes()

    response = await client.post("/api/v1/resumes", files={"file": ("resume.pdf", data, "application/pdf")})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "400"


@pytest.mark.asyncio
async def test_wrong_magic_bytes_job_upload_is_rejected(client):
    data = (SECURITY_FIXTURES / "wrong_magic_bytes.docx").read_bytes()

    response = await client.post(
        "/api/v1/jobs",
        files={"file": ("job.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_xxe_payload_docx_resume_upload_is_rejected_and_does_not_leak_file_contents(client):
    data = (SECURITY_FIXTURES / "xxe_payload.docx").read_bytes()

    response = await client.post(
        "/api/v1/resumes",
        files={"file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 400
    # No resolved /etc/passwd content anywhere in the response — the
    # entity was never resolved at all (rejected pre-parse), not just
    # resolved-and-then-hidden.
    assert "root:" not in response.text
