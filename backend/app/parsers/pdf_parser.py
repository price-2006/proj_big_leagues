"""PDF -> raw text + layout metadata, via PyMuPDF (see docs/ARCHITECTURE.md §6).

Takes raw bytes rather than a file path so the same function serves an
uploaded file (Phase 8) and dataset text run through this parser for
train/serve consistency (docs/DATASET_STRATEGY.md §4).

A timeout guard against adversarial/malformed files and a hard upload size
cap are Phase 14 (security hardening) concerns, not this module's; here we
only guarantee that a corrupt file raises DocumentParseError instead of
crashing or hanging on a well-formed-but-huge one.
"""
import pymupdf

from app.parsers.exceptions import DocumentParseError
from app.schemas.document import ParsedDocument, TextLine

_BOLD_FLAG = 1 << 4  # PyMuPDF span "flags" bit 4


def parse_pdf(data: bytes) -> ParsedDocument:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise DocumentParseError(f"Could not open PDF: {exc}") from exc

    try:
        if doc.page_count == 0:
            raise DocumentParseError("PDF has no pages")

        lines: list[TextLine] = []
        text_parts: list[str] = []
        try:
            for page_index in range(doc.page_count):
                page_dict = doc[page_index].get_text("dict")
                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:  # skip image/non-text blocks
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        line_text = "".join(span.get("text", "") for span in spans).strip()
                        if not line_text:
                            continue
                        lines.append(
                            TextLine(
                                text=line_text,
                                font_size=max((span.get("size", 0.0) for span in spans), default=None),
                                bold=any(_is_bold(span) for span in spans),
                                page_number=page_index + 1,
                                bbox=tuple(line.get("bbox", (0.0, 0.0, 0.0, 0.0))),
                            )
                        )
                        text_parts.append(line_text)
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError(f"Failed while extracting PDF text: {exc}") from exc

        if not text_parts:
            raise DocumentParseError(
                "No extractable text found in PDF (possibly a scanned/image-only document)"
            )

        return ParsedDocument(
            file_type="pdf",
            raw_text="\n".join(text_parts),
            lines=lines,
            page_count=doc.page_count,
        )
    finally:
        doc.close()


def _is_bold(span: dict) -> bool:
    return bool(span.get("flags", 0) & _BOLD_FLAG) or "bold" in span.get("font", "").lower()
