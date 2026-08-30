"""Dataset-specific text repair (Phase 10, docs/DATASET_STRATEGY.md §4's
"normalize encoding/whitespace" preprocessing step) — scoped to the
dataset ingestion pipeline only, never touching Phase 1-4's parsers that
real user uploads go through.

Discovered by actually running extraction on real dataset rows: the
cnamuangtoun resume_text field has section headers glued directly to the
following content with no separator at all — "SummaryHighly motivated
Sales Associate...", "ExperienceAccountant,08/2014-05/2015..." — a lost-
line-break artifact from whatever process extracted this dataset's text
(most likely PDF-to-text). Confirmed consistent across every sample row
checked, not a one-off. Phase 2's section detector on plain text (no
bold/font metadata to fall back on) can only find a header via its alias
table, and an alias can't match text mashed into the following word —
this is exactly the whitespace-normalization gap §4 already anticipated,
not a new problem invented here.
"""
import re

# Keywords that are recognized aliases in app/nlp/section_detector.py's
# alias table (plus "Highlights", added there alongside this fix) — a
# keyword not in that table would get isolated onto its own line here for
# nothing, since the plain-text section detector can only recognize a
# header via alias match (no bold/font metadata to fall back on).
_HEADER_KEYWORDS = (
    "Professional Summary",
    "Summary",
    "Highlights",
    "Professional Experience",
    "Work Experience",
    "Employment History",
    "Experience",
    "Education",
    "Skills",
    "Technical Skills",
    "Objective",
    "Certifications",
)

# Longest-first so "Professional Summary" matches before the bare "Summary"
# substring inside it does.
_GLUED_HEADER_RE = re.compile(
    r"\b(" + "|".join(sorted(_HEADER_KEYWORDS, key=len, reverse=True)) + r")(?=[A-Z])"
)


def insert_missing_header_breaks(text: str) -> str:
    """'SummaryHighly motivated...' -> 'Summary\\nHighly motivated...'.
    Only fires when a keyword is immediately followed by an uppercase
    letter with zero separating whitespace — real headers that already
    have a line break or a space are left untouched.
    """
    return _GLUED_HEADER_RE.sub(r"\1\n", text)
