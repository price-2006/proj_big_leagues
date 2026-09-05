"""Loads cnamuangtoun/resume-job-description-fit (Phase 10) — the one
public source with direct resume<->JD relevance labels
(docs/DATASET_STRATEGY.md §2.1). Public, ungated, on Hugging Face; no
account needed, confirmed via the HF API before writing this (`gated:
false, private: false`).

The dataset ships its own train.csv/test.csv split, which this loader
deliberately ignores and instead concatenates into one pool — verified
for real that the shipped split leaks: 476 of 477 unique resumes in
test.csv also appear in train.csv. app/services/dataset_sources/grouped_split.py
is what actually produces this project's train/val/test assignment.

Labels: a 3-way category ('No Fit' / 'Potential Fit' / 'Good Fit'),
confirmed against the real downloaded file — mapped to a 0-1 scale.
Label provenance is undocumented by the dataset itself
(docs/DATASET_STRATEGY.md §2.1), so this is tagged 'dataset:cnamuangtoun',
never blended with the weak-supervision or human-annotated sources.
"""
import csv
import hashlib
import io
import urllib.request
from dataclasses import dataclass

TRAIN_URL = "https://huggingface.co/datasets/cnamuangtoun/resume-job-description-fit/resolve/main/train.csv"
TEST_URL = "https://huggingface.co/datasets/cnamuangtoun/resume-job-description-fit/resolve/main/test.csv"

LABEL_SOURCE = "dataset:cnamuangtoun"

# Confirmed against the real downloaded CSV (3 distinct values, no others).
_LABEL_MAP = {"No Fit": 0.0, "Potential Fit": 0.5, "Good Fit": 1.0}


@dataclass(frozen=True)
class FitRow:
    resume_text: str
    job_text: str
    label: float

    @property
    def resume_ref(self) -> str:
        return _stable_hash(self.resume_text)

    @property
    def job_ref(self) -> str:
        return _stable_hash(self.job_text)


def fetch_csv(url: str, timeout: int = 60) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_fit_rows(csv_text: str) -> list[FitRow]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        label = _LABEL_MAP.get(row["label"].strip())
        if label is None:
            raise ValueError(f"Unrecognized label value: {row['label']!r}")
        rows.append(FitRow(resume_text=row["resume_text"], job_text=row["job_description_text"], label=label))
    return rows


def load_combined_pool() -> list[FitRow]:
    """Fetches both files and concatenates them — see module docstring
    for why the dataset's own train/test boundary isn't used."""
    train_rows = parse_fit_rows(fetch_csv(TRAIN_URL))
    test_rows = parse_fit_rows(fetch_csv(TEST_URL))
    return train_rows + test_rows


def dedupe_unique_texts(rows: list[FitRow]) -> tuple[dict[str, str], dict[str, str]]:
    """Returns (resume_ref -> resume_text, job_ref -> job_text) for every
    *unique* text across the pool — the 8,000 rows are ~643 unique
    resumes x ~351 unique jobs (docs/DATASET_STRATEGY.md §2.1's
    duplication problem), so this is what actually needs parsing/
    extracting, not 8,000 redundant passes through spaCy."""
    resumes = {row.resume_ref: row.resume_text for row in rows}
    jobs = {row.job_ref: row.job_text for row in rows}
    return resumes, jobs


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
