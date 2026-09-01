"""Routes an uploaded file to the right Phase 1 parser by extension
(Phase 8). Magic-byte content-type sniffing (docs/ARCHITECTURE.md §12)
happens earlier, in app/services/upload_validation.py, against the raw
bytes before this module is even reached — this stays extension-based
for routing since by that point the signature is already verified.
"""
import asyncio
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.parsers.docx_parser import parse_docx
from app.parsers.exceptions import DocumentParseError
from app.parsers.pdf_parser import parse_pdf
from app.schemas.document import ParsedDocument

_PARSERS = {"pdf": parse_pdf, "docx": parse_docx}

# Phase 14 (docs/ARCHITECTURE.md §12): a timeout guard against a
# well-formed-but-adversarial file (e.g. a PDF/DOCX crafted to make the
# parser spin far longer than any real resume/JD would need). Bounds how
# long a request waits — the parse runs off the event loop in a thread
# (starlette's run_in_threadpool) so a slow parse can't also stall every
# other concurrent request — and turns a hang into a clean error instead
# of an indefinitely pending response. It does not, and structurally
# cannot, kill the underlying CPython thread if the library call itself
# never returns; that residual worker-pinning risk is a known limitation
# of any same-process timeout, not silently unaddressed — a hard kill
# would need running the parse in a separate process, which isn't a
# proportionate amount of infrastructure for this project's scale.
PARSE_TIMEOUT_SECONDS = 10.0


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in _PARSERS:
        raise DocumentParseError(f"Unsupported file type '.{ext}' — only .pdf and .docx are supported")
    return ext


def parse_uploaded_document(filename: str, data: bytes) -> ParsedDocument:
    file_type = detect_file_type(filename)
    return _PARSERS[file_type](data)


async def parse_uploaded_document_with_timeout(
    filename: str, data: bytes, timeout_seconds: float = PARSE_TIMEOUT_SECONDS
) -> ParsedDocument:
    try:
        return await asyncio.wait_for(run_in_threadpool(parse_uploaded_document, filename, data), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise DocumentParseError(
            f"Parsing exceeded the {timeout_seconds:.0f}s time limit — the file may be malformed or adversarial"
        ) from exc
