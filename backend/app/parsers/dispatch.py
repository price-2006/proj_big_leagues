"""Routes an uploaded file to the right Phase 1 parser by extension
(Phase 8). Real magic-byte content-type sniffing is a Phase 14 concern
(docs/ARCHITECTURE.md §12) — this is extension-based, matching what Phase
1-7 have relied on so far.
"""
from pathlib import Path

from app.parsers.docx_parser import parse_docx
from app.parsers.exceptions import DocumentParseError
from app.parsers.pdf_parser import parse_pdf
from app.schemas.document import ParsedDocument

_PARSERS = {"pdf": parse_pdf, "docx": parse_docx}


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in _PARSERS:
        raise DocumentParseError(f"Unsupported file type '.{ext}' — only .pdf and .docx are supported")
    return ext


def parse_uploaded_document(filename: str, data: bytes) -> ParsedDocument:
    file_type = detect_file_type(filename)
    return _PARSERS[file_type](data)
