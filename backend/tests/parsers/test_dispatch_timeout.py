"""Phase 14 (docs/ARCHITECTURE.md §12): a timeout guard against a
malformed/adversarial file that makes the parser hang. Tested against a
monkeypatched slow parser rather than a genuinely hang-inducing PDF/DOCX
— constructing a real one deterministically (without relying on a
specific PyMuPDF/lxml version's own behavior) isn't practical, and the
guard itself (asyncio.wait_for around a threadpool call) doesn't care
which library is slow underneath it.
"""
import asyncio
import time

import pytest

from app.parsers import dispatch
from app.parsers.exceptions import DocumentParseError


def test_timeout_guard_raises_a_clean_error_instead_of_hanging(monkeypatch):
    def _slow_parse(data: bytes):
        time.sleep(5)
        raise AssertionError("should have been aborted by the timeout well before returning")

    monkeypatch.setitem(dispatch._PARSERS, "pdf", _slow_parse)

    with pytest.raises(DocumentParseError, match="time limit"):
        asyncio.run(dispatch.parse_uploaded_document_with_timeout("resume.pdf", b"data", timeout_seconds=0.2))


def test_a_fast_parse_within_the_timeout_returns_normally(monkeypatch):
    from app.schemas.document import ParsedDocument

    def _fast_parse(data: bytes) -> ParsedDocument:
        return ParsedDocument(file_type="pdf", raw_text="fine", lines=[])

    monkeypatch.setitem(dispatch._PARSERS, "pdf", _fast_parse)

    result = asyncio.run(dispatch.parse_uploaded_document_with_timeout("resume.pdf", b"data", timeout_seconds=5.0))
    assert result.raw_text == "fine"
