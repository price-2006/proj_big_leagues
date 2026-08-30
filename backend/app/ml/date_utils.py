"""Lightweight date-range math for the years_experience_match feature
(Phase 7, docs/ARCHITECTURE.md §8). Resume experience entries keep
start_date/end_date as raw strings by design (Phase 3 deferred date math
to whichever phase actually needed it) — this is that phase.
"""
import re
from datetime import date

_MONTH_YEAR_RE = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})$")
_YEAR_ONLY_RE = re.compile(r"^(?P<year>\d{4})$")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip


def parse_resume_date(text: str | None, as_of: date) -> date | None:
    """Unparseable or missing text returns None (excluded from the span
    calculation below). 'Present'/'Current' resolve to `as_of`."""
    if not text:
        return None
    text = text.strip()
    if text.lower() in ("present", "current"):
        return as_of

    match = _MONTH_YEAR_RE.match(text)
    if match:
        month = _MONTHS.get(match.group("month")[:3].lower())
        if month:
            return date(int(match.group("year")), month, 1)

    match = _YEAR_ONLY_RE.match(text)
    if match:
        return date(int(match.group("year")), 1, 1)

    return None


def total_experience_years(entries: list[tuple[str | None, str | None]], as_of: date) -> float:
    """`entries`: (start_date, end_date) raw strings, one pair per resume
    experience entry. Uses the span from the earliest parseable start to
    the latest parseable end (or `as_of`, if any entry is ongoing) —
    not a sum of individual entries' durations, since summing would
    double-count overlapping/concurrent roles. Known limitation: this
    also doesn't subtract genuine employment gaps between roles.
    """
    starts = [d for d in (parse_resume_date(s, as_of) for s, _ in entries) if d is not None]
    ends = [d for d in (parse_resume_date(e, as_of) for _, e in entries) if d is not None]
    if not starts or not ends:
        return 0.0
    return max((max(ends) - min(starts)).days / 365.25, 0.0)
