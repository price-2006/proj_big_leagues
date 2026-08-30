"""Seniority-level inference from a job title string — shared between the
JD-side extractor (Phase 4) and Feature Engineering's seniority_match
feature (Phase 7, docs/ARCHITECTURE.md §8), so both sides of the match
use identical rules rather than two copies that could drift apart.
"""
from app.schemas.job_profile import SeniorityLevel

_STAFF_CUES = ("staff", "principal", "distinguished")
_SENIOR_CUES = ("senior", "sr.")
_JUNIOR_CUES = ("junior", "jr.", "entry level", "entry-level", "associate")
_MID_CUES = ("mid-level", "mid level", "intermediate")


def detect_seniority_from_title(title: str | None) -> SeniorityLevel:
    if not title:
        return SeniorityLevel.UNSPECIFIED
    lowered = title.lower()
    if any(cue in lowered for cue in _STAFF_CUES):
        return SeniorityLevel.STAFF
    if any(cue in lowered for cue in _SENIOR_CUES):
        return SeniorityLevel.SENIOR
    if any(cue in lowered for cue in _JUNIOR_CUES):
        return SeniorityLevel.JUNIOR
    if any(cue in lowered for cue in _MID_CUES):
        return SeniorityLevel.MID
    return SeniorityLevel.UNSPECIFIED
