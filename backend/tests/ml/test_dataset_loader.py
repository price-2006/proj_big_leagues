"""Phase 11: dataset_loader.py turns training_labels rows + parsed
profiles into feature matrices. Covers the caching wrapper (the actual
reason this module exists rather than reusing feature_engineering.py
directly against 10k pairs) and the missing-profile skip path (real
condition — a training_labels row can reference a resume/job ref that
build_dataset.py never wrote to data/processed/, e.g. after a --max-jobs
limited run).
"""
from app.ml.dataset_loader import (
    EMBEDDING_COSINE_BASELINE_COLUMN,
    FEATURE_NAMES,
    _CachingEmbeddingService,
    build_labeled_examples,
    to_dataframe,
)
from app.models.training_label import TrainingLabel
from app.schemas.candidate_profile import CandidateProfile, ContactInfo, ExperienceEntry
from app.schemas.job_profile import JobProfile, RequirementItem, RequirementLevel, SeniorityLevel
from app.services.skill_normalization_service import SkillTaxonomy


class FakeEmbeddingService:
    model_name = "fake"
    dimension = 4

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(t) % 7 + 1), 1.0, 0.0, 0.0] for t in texts]


def _row(resume_ref: str, job_ref: str, label: float = 0.5, label_source: str = "test", split: str = "train") -> TrainingLabel:
    return TrainingLabel(
        external_resume_ref=resume_ref, external_job_ref=job_ref, label=label, label_source=label_source, dataset_split=split
    )


def _resume() -> CandidateProfile:
    return CandidateProfile(
        contact=ContactInfo(),
        skills=["Python"],
        experience=[
            ExperienceEntry(
                title="Backend Engineer",
                start_date="2020-01-01",
                end_date=None,
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


def test_caching_embedding_service_embeds_each_unique_text_once():
    fake = FakeEmbeddingService()
    cached = _CachingEmbeddingService(fake)

    first = cached.embed(["a", "b", "a"])
    second = cached.embed(["a", "c"])

    assert first[0] == first[2]  # same text -> same vector, from one call
    assert second[0] == first[0]  # cached across calls, not just within one
    all_requested = [t for call in fake.calls for t in call]
    assert all_requested.count("a") == 1  # "a" only ever reached the inner service once
    assert set(all_requested) == {"a", "b", "c"}


def test_build_labeled_examples_skips_rows_with_missing_profiles():
    taxonomy = SkillTaxonomy([], [])
    resume_profiles = {"r1": _resume()}
    job_profiles = {"j1": _job()}
    rows = [_row("r1", "j1"), _row("r1", "missing-job"), _row("missing-resume", "j1")]

    examples = build_labeled_examples(rows, resume_profiles, job_profiles, taxonomy, FakeEmbeddingService())

    assert len(examples) == 1
    assert examples[0].resume_ref == "r1"
    assert examples[0].job_ref == "j1"


def test_to_dataframe_has_one_row_per_example_and_all_feature_columns():
    taxonomy = SkillTaxonomy([], [])
    rows = [_row("r1", "j1", label=0.9, label_source="src-a", split="train")]
    examples = build_labeled_examples(rows, {"r1": _resume()}, {"j1": _job()}, taxonomy, FakeEmbeddingService())

    df = to_dataframe(examples)

    assert len(df) == 1
    assert set(FEATURE_NAMES) <= set(df.columns)
    assert EMBEDDING_COSINE_BASELINE_COLUMN in df.columns
    assert df.iloc[0]["label"] == 0.9
    assert df.iloc[0]["label_source"] == "src-a"
    assert df.iloc[0]["dataset_split"] == "train"
