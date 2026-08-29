"""Shared output contract for both document parsers (Phase 1).

PDF and DOCX carry different native layout metadata, so this schema unifies
them into one shape the section detector (Phase 2) can consume without
caring which file type produced it. Fields only one file type can populate
(page_number/bbox for PDF, style_name for DOCX) are None on the other.
"""
from typing import Literal

from pydantic import BaseModel


class TextLine(BaseModel):
    text: str
    font_size: float | None = None
    bold: bool = False
    page_number: int | None = None  # PDF only
    bbox: tuple[float, float, float, float] | None = None  # PDF only: x0, y0, x1, y1
    style_name: str | None = None  # DOCX only, e.g. "Heading 1", "Normal"


class ParsedDocument(BaseModel):
    file_type: Literal["pdf", "docx"]
    raw_text: str
    lines: list[TextLine]
    page_count: int | None = None  # PDF only
