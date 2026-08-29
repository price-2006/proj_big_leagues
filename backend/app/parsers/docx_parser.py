"""DOCX -> raw text + layout metadata, via python-docx (see docs/ARCHITECTURE.md §6).

DOCX has no page-position concept the way PDF does; its layout signal is
structural instead — paragraph style name ("Heading 1", "Normal", ...) plus
run-level bold/font-size, which is what the Phase 2 section detector reads
in place of PDF's bbox/font-size heuristics.
"""
from io import BytesIO

import docx
from docx.text.paragraph import Paragraph

from app.parsers.exceptions import DocumentParseError
from app.schemas.document import ParsedDocument, TextLine


def parse_docx(data: bytes) -> ParsedDocument:
    try:
        document = docx.Document(BytesIO(data))
    except Exception as exc:
        raise DocumentParseError(f"Could not open DOCX: {exc}") from exc

    lines: list[TextLine] = []
    text_parts: list[str] = []
    try:
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            font_size, bold = _run_style(paragraph)
            lines.append(
                TextLine(
                    text=text,
                    font_size=font_size,
                    bold=bold,
                    style_name=paragraph.style.name if paragraph.style else None,
                )
            )
            text_parts.append(text)
    except Exception as exc:
        raise DocumentParseError(f"Failed while extracting DOCX text: {exc}") from exc

    if not text_parts:
        raise DocumentParseError("No extractable text found in DOCX")

    return ParsedDocument(file_type="docx", raw_text="\n".join(text_parts), lines=lines)


def _run_style(paragraph: Paragraph) -> tuple[float | None, bool]:
    """Font size/bold come from the runs; fall back to the paragraph style
    when no run overrides it (most resume body text doesn't)."""
    sizes = [run.font.size.pt for run in paragraph.runs if run.font.size is not None]
    bold = any(run.bold for run in paragraph.runs if run.bold is not None)

    style_font = paragraph.style.font if paragraph.style else None
    font_size = max(sizes) if sizes else (style_font.size.pt if style_font and style_font.size else None)
    if not bold and style_font is not None:
        bold = bool(style_font.bold)

    return font_size, bold
