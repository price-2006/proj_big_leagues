"""Phase 14, docs/ARCHITECTURE.md §12: "raw PII is never sent to the LLM
provider beyond what's needed for the explanation task." This was
already true by construction since Phase 12 (build_prompt only ever
reads summary/experience/skills/job text — never candidate.contact), but
had no regression test locking it in until now.
"""
from app.schemas.candidate_profile import CandidateProfile, ContactInfo, ExperienceEntry
from app.schemas.job_profile import JobProfile, RequirementItem, RequirementLevel, SeniorityLevel
from app.schemas.match_features import SkillBreakdown
from app.services.explanation_service import build_prompt

_PII_NAME = "Alexandra Q. Testperson"
_PII_EMAIL = "alexandra.testperson@example.com"
_PII_PHONE = "555-867-5309"


def _candidate() -> CandidateProfile:
    return CandidateProfile(
        contact=ContactInfo(name=_PII_NAME, email=_PII_EMAIL, phone=_PII_PHONE, location="Nowhere, USA"),
        summary="Backend engineer",
        skills=["Python"],
        experience=[
            ExperienceEntry(
                title="Backend Engineer", organization="Acme", start_date="2020-01", end_date=None,
                bullets=["Built backend services in Python"],
            )
        ],
    )


def _job() -> JobProfile:
    return JobProfile(
        title="Backend Engineer",
        seniority=SeniorityLevel.MID,
        requirements=[RequirementItem(text="Python required", level=RequirementLevel.REQUIRED, skills=["Python"])],
        responsibilities=["Build backend services"],
    )


def test_prompt_never_contains_the_candidates_name_email_or_phone():
    breakdown = SkillBreakdown(matched_required=["Python"], missing_required=[], matched_preferred=[], missing_preferred=[])
    prompt = build_prompt(_candidate(), _job(), breakdown, rule_based_score=80.0)

    assert _PII_NAME not in prompt
    assert _PII_EMAIL not in prompt
    assert _PII_PHONE not in prompt
    # What it should contain, to confirm this isn't just an empty/broken prompt.
    assert "Built backend services in Python" in prompt
