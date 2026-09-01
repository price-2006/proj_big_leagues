"""Phase 14 test procedure per docs/ROADMAP.md: "oversized file rejected,
wrong-magic-byte file rejected." Unit-level coverage of the two checks
themselves; tests/api/test_upload_security.py exercises them through the
real POST /resumes and /jobs endpoints.
"""
import io

import pytest
from fastapi import UploadFile

from app.services.upload_validation import (
    UnrecognizedFileSignatureError,
    UploadTooLargeError,
    read_upload_within_limit,
    verify_magic_bytes,
)


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="test")


@pytest.mark.asyncio
async def test_read_within_limit_returns_full_content_when_under_the_cap():
    data = b"small file content"
    result = await read_upload_within_limit(_upload(data), max_bytes=1024)
    assert result == data


@pytest.mark.asyncio
async def test_read_within_limit_raises_as_soon_as_the_cap_is_exceeded():
    data = b"x" * 1000
    with pytest.raises(UploadTooLargeError) as exc_info:
        await read_upload_within_limit(_upload(data), max_bytes=500)
    assert exc_info.value.max_bytes == 500


@pytest.mark.asyncio
async def test_read_within_limit_accepts_content_exactly_at_the_cap():
    data = b"x" * 500
    result = await read_upload_within_limit(_upload(data), max_bytes=500)
    assert result == data


def test_verify_magic_bytes_accepts_a_real_pdf_signature():
    verify_magic_bytes(b"%PDF-1.4 rest of the file...", "pdf")  # does not raise


def test_verify_magic_bytes_accepts_a_real_docx_zip_signature():
    verify_magic_bytes(b"PK\x03\x04 rest of the zip...", "docx")  # does not raise


def test_verify_magic_bytes_rejects_pdf_extension_with_non_pdf_content():
    with pytest.raises(UnrecognizedFileSignatureError) as exc_info:
        verify_magic_bytes(b"#!/bin/sh\necho not a pdf\n", "pdf")
    assert exc_info.value.file_type == "pdf"


def test_verify_magic_bytes_rejects_docx_extension_with_non_zip_content():
    with pytest.raises(UnrecognizedFileSignatureError):
        verify_magic_bytes(b"this is plain text, not a zip", "docx")


def test_verify_magic_bytes_is_a_noop_for_an_unrecognized_file_type():
    verify_magic_bytes(b"anything at all", "txt")  # no signature registered — nothing to check
