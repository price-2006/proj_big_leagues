"""Plain pasted text -> ParsedDocument (Phase 4, docs/ARCHITECTURE.md §2's
"JD Text Extractor"). The counterpart to pdf_parser/docx_parser for job
descriptions submitted as pasted text rather than an uploaded file — an
uploaded JD file reuses parse_pdf/parse_docx directly, no separate JD
parser needed for that path.

No layout metadata exists for plain text, so every TextLine here has
font_size=None, bold=False, style_name=None; the JD section detector
(Phase 4) falls back to text-position heuristics (the first line as the
title) rather than the bold/font-size signals Phase 1's parsers provide.
"""
from app.parsers.exceptions import DocumentParseError
from app.schemas.document import ParsedDocument, TextLine


def parse_text(text: str) -> ParsedDocument:
    lines = [TextLine(text=stripped) for raw in text.splitlines() if (stripped := raw.strip())]
    if not lines:
        raise DocumentParseError("No extractable text found")
    return ParsedDocument(file_type="text", raw_text="\n".join(line.text for line in lines), lines=lines)
