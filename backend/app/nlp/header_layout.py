"""Shared line-segmentation primitives for header-alias + layout-heuristic
detection, used by both the resume section detector (Phase 2) and the JD
requirement detector (Phase 4). The underlying algorithm — walk lines,
match a known header phrase or fall back to a layout signal, split into
segments — is identical between the two; only the alias table and the
section-type enum differ per caller.
"""
import re
from collections.abc import Callable
from statistics import median
from typing import TypeVar

from app.schemas.document import TextLine

T = TypeVar("T")

_MAX_HEADER_WORDS = 5
_FONT_SIZE_HEADER_RATIO = 1.15


def normalize_header(text: str) -> str:
    text = text.lower().strip().replace("&", "and")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def estimate_body_font_size(lines: list[TextLine]) -> float | None:
    sizes = [line.font_size for line in lines if line.font_size is not None]
    return median(sizes) if sizes else None


def looks_like_header(line: TextLine, body_font_size: float | None) -> bool:
    word_count = len(line.text.split())
    if word_count == 0 or word_count > _MAX_HEADER_WORDS:
        return False
    if line.style_name and line.style_name.lower().startswith(("heading", "title")):
        return True
    if line.bold:
        return True
    if body_font_size and line.font_size and line.font_size > body_font_size * _FONT_SIZE_HEADER_RATIO:
        return True
    return line.text.isupper()


def segment_by_alias_headers(
    lines: list[TextLine],
    match_alias: Callable[[str], T | None],
    default_type: T,
    fallback_type: T,
) -> list[tuple[T, str | None, list[TextLine]]]:
    """Walk `lines`, starting a new segment whenever a line matches a known
    header phrasing (via `match_alias`) or looks like a header by layout
    alone (typed `fallback_type` in that case). Returns (type, raw_header,
    content_lines) tuples; the degenerate leading segment (no header, no
    content) is dropped, but a real header with zero content lines under
    it is kept.
    """
    body_font_size = estimate_body_font_size(lines)
    segments: list[tuple[T, str | None, list[TextLine]]] = []
    current_type = default_type
    current_header: str | None = None
    current_lines: list[TextLine] = []

    for line in lines:
        matched = match_alias(line.text)
        if matched is None and looks_like_header(line, body_font_size):
            matched = fallback_type

        if matched is not None:
            segments.append((current_type, current_header, current_lines))
            current_type, current_header, current_lines = matched, line.text, []
        else:
            current_lines.append(line)

    segments.append((current_type, current_header, current_lines))
    return [s for s in segments if s[2] or s[1]]
