"""Loads Phase 10's output (training_labels + backend/data/processed/*.json)
into feature matrices for Phase 11's models — the one place both
train_model.py and evaluate.py go for training/eval data, so they can
never silently drift onto different feature-computation logic.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_engineering import compute_feature_vector
from app.models.training_label import TrainingLabel
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile
from app.schemas.match_features import FeatureVector
from app.services.embedding_service import EmbeddingService, cosine_similarity
from app.services.skill_normalization_service import SkillTaxonomy

# Same reasoning as build_dataset.py's PROCESSED_DIR: this only ever runs
# inside the backend container, which bind-mounts ./backend, not the repo
# root — so this resolves to backend/data/processed/, not the repo-root
# data/processed/ that data/README.md's directory layout describes.
PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
FEATURE_MATRIX_PATH = PROCESSED_DIR / "feature_matrix.csv"

FEATURE_NAMES: list[str] = list(FeatureVector.model_fields.keys())
EMBEDDING_COSINE_BASELINE_COLUMN = "embedding_cosine_baseline"


@dataclass(frozen=True)
class LabeledExample:
    resume_ref: str
    job_ref: str
    label: float
    label_source: str
    dataset_split: str
    features: FeatureVector
    embedding_cosine_baseline: float


class _CachingEmbeddingService:
    """Memoizes embed() by exact text string. Phase 10's ~10k training
    pairs are built from only 643 unique resumes and 351 unique jobs, so
    the same bullets/responsibilities/summaries recur across thousands of
    pairs — without this, feature extraction re-embeds identical text
    thousands of times over. Scoped to this training-data loading path
    only; the live inference path (match_pipeline.py) scores one pair at
    a time and has no such redundancy to cache."""

    def __init__(self, inner: EmbeddingService) -> None:
        self._inner = inner
        self._cache: dict[str, list[float]] = {}

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        uncached = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if uncached:
            for text, vector in zip(uncached, self._inner.embed(uncached)):
                self._cache[text] = vector
        return [self._cache[t] for t in texts]


def _embedding_cosine_baseline(candidate: CandidateProfile, job: JobProfile, embedding_service: EmbeddingService) -> float:
    """docs/ARCHITECTURE.md §13's "plain embedding-cosine-similarity
    baseline": one whole-document embedding per side (no structure
    awareness — every existing feature is deliberately more granular
    than this), so it's a genuinely different, simpler approach to
    compare the trained models against, not a repackaged feature."""
    candidate_text = " ".join(
        [
            candidate.summary or "",
            ", ".join(candidate.skills),
            " ".join(b for e in candidate.experience for b in e.bullets),
            " ".join(b for e in candidate.projects for b in e.bullets),
        ]
    ).strip()
    job_text = " ".join(
        [
            job.title or "",
            job.about or "",
            " ".join(job.responsibilities),
            " ".join(item.text for item in job.requirements),
        ]
    ).strip()
    if not candidate_text or not job_text:
        return 0.0
    [candidate_vec, job_vec] = embedding_service.embed([candidate_text, job_text])
    return cosine_similarity(candidate_vec, job_vec)


def load_processed_profiles() -> tuple[dict[str, CandidateProfile], dict[str, JobProfile]]:
    resumes = json.loads((PROCESSED_DIR / "resume_profiles.json").read_text())
    jobs = json.loads((PROCESSED_DIR / "job_profiles.json").read_text())
    return (
        {ref: CandidateProfile.model_validate(p) for ref, p in resumes.items()},
        {ref: JobProfile.model_validate(p) for ref, p in jobs.items()},
    )


async def load_training_label_rows(session: AsyncSession) -> list[TrainingLabel]:
    """Only external-ref rows — the only kind Phase 10 has produced so
    far (see app/models/training_label.py); resume_id/job_id-keyed rows
    against real uploads don't exist yet, so there's nothing to join
    against for them."""
    result = await session.execute(select(TrainingLabel).where(TrainingLabel.external_resume_ref.is_not(None)))
    return list(result.scalars().all())


def build_labeled_examples(
    rows: list[TrainingLabel],
    resume_profiles: dict[str, CandidateProfile],
    job_profiles: dict[str, JobProfile],
    taxonomy: SkillTaxonomy,
    embedding_service: EmbeddingService,
) -> list[LabeledExample]:
    cached_embeddings = _CachingEmbeddingService(embedding_service)
    examples: list[LabeledExample] = []
    skipped = 0
    for i, row in enumerate(rows, 1):
        candidate = resume_profiles.get(row.external_resume_ref)
        job = job_profiles.get(row.external_job_ref)
        if candidate is None or job is None:
            skipped += 1
            continue
        features = compute_feature_vector(candidate, job, taxonomy, cached_embeddings)
        baseline = _embedding_cosine_baseline(candidate, job, cached_embeddings)
        examples.append(
            LabeledExample(
                resume_ref=row.external_resume_ref,
                job_ref=row.external_job_ref,
                label=float(row.label),
                label_source=row.label_source,
                dataset_split=row.dataset_split,
                features=features,
                embedding_cosine_baseline=baseline,
            )
        )
        if i % 1000 == 0:
            print(f"  {i}/{len(rows)} feature vectors computed ({skipped} skipped so far)")
    print(f"  done: {len(examples)} feature vectors, {skipped} skipped (profile missing from data/processed/)")
    return examples


def to_dataframe(examples: list[LabeledExample]) -> pd.DataFrame:
    """One row per example: the 10 named features, plus label/label_source/
    dataset_split/resume_ref/job_ref for splitting, grouping, and
    per-source metric breakdowns downstream."""
    records = [
        {
            **ex.features.model_dump(),
            EMBEDDING_COSINE_BASELINE_COLUMN: ex.embedding_cosine_baseline,
            "label": ex.label,
            "label_source": ex.label_source,
            "dataset_split": ex.dataset_split,
            "resume_ref": ex.resume_ref,
            "job_ref": ex.job_ref,
        }
        for ex in examples
    ]
    return pd.DataFrame.from_records(records)


async def load_or_build_feature_matrix(
    session: AsyncSession,
    taxonomy: SkillTaxonomy,
    embedding_service: EmbeddingService,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """train_model.py and evaluate.py both call this — feature/baseline
    computation is expensive (embedding calls per pair, even cached) and
    purely a function of training_labels + data/processed/*.json, so it's
    computed once and cached to FEATURE_MATRIX_PATH rather than redone on
    every run of either script."""
    if FEATURE_MATRIX_PATH.exists() and not force_rebuild:
        return pd.read_csv(FEATURE_MATRIX_PATH)

    resume_profiles, job_profiles = load_processed_profiles()
    rows = await load_training_label_rows(session)
    examples = build_labeled_examples(rows, resume_profiles, job_profiles, taxonomy, embedding_service)
    df = to_dataframe(examples)
    FEATURE_MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FEATURE_MATRIX_PATH, index=False)
    return df
