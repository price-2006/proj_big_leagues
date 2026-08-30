"""Build the training dataset (Phase 10, docs/ROADMAP.md).

Lives in backend/scripts/, not the top-level scripts/ the roadmap names
literally — same reasoning as seed_skills.py/embed_skills.py (Phase 5):
it needs spaCy (via app.nlp.information_extraction, for resume
extraction) which only reliably works inside the backend Docker
container on this machine, and that container only bind-mounts
./backend, not the repo root (docker-compose.yml).

Pipeline:
  1. Fetch cnamuangtoun/resume-job-description-fit (both files, combined
     into one pool — the dataset's own train/test split leaks, see
     app/services/dataset_sources/cnamuangtoun_loader.py).
  2. Dedupe to unique resume/job texts; run each through this product's
     OWN parsers (parse_text -> section detect -> extract profile) —
     train-time features computed by the exact inference-time code path
     (docs/DATASET_STRATEGY.md §4).
  3. Infer an O*NET occupation for each unique resume/job (from its
     title), for occupation-family weak supervision.
  4. Generate three independently-tagged label sets: the dataset's own
     fit labels, occupation-family positive/negative pairs, and
     rule-based-score-derived tiers (Phase 7's real scorer, on a sampled
     subset — full cross-product is 643*351 =~ 226k pairs, each needing
     several embedding calls, which is not a proportionate amount of
     compute for a portfolio-scale project).
  5. Group-split the combined row set (grouped_split.py) so no resume or
     job text crosses a train/val/test boundary.
  6. Write parsed profiles to data/processed/ (JSON, not the production
     resumes/jobs tables — those are for real user uploads) and every
     label row to training_labels.

Run (inside the backend container, per docs/ROADMAP.md's Phase 10 note
that this needs spaCy):
    docker exec resume_matcher_backend python -m scripts.build_dataset [--max-resumes N] [--max-rule-based-pairs N]
"""
import argparse
import asyncio
import json
import random
import time
from decimal import Decimal
from pathlib import Path
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.ml.feature_engineering import compute_feature_vector
from app.ml.rule_based_scorer import score
from app.models.training_label import TrainingLabel
from app.nlp.information_extraction import extract_candidate_profile
from app.nlp.jd_section_detector import detect_jd_sections
from app.nlp.job_information_extraction import extract_job_profile
from app.nlp.section_detector import detect_sections
from app.parsers.exceptions import DocumentParseError
from app.parsers.text_parser import parse_text
from app.schemas.candidate_profile import CandidateProfile
from app.schemas.job_profile import JobProfile
from app.services.dataset_sources.cnamuangtoun_loader import LABEL_SOURCE as CNAMUANGTOUN_LABEL_SOURCE
from app.services.dataset_sources.cnamuangtoun_loader import dedupe_unique_texts, load_combined_pool
from app.services.dataset_sources.grouped_split import DatasetRow, find_leakage, group_split
from app.services.dataset_sources.text_cleanup import insert_missing_header_breaks
from app.services.dataset_sources.weak_supervision import (
    OCCUPATION_LABEL_SOURCE,
    RULE_BASED_LABEL_SOURCE,
    occupation_pair_label,
    rule_based_tier_label,
)
from app.services.embedding_service import get_embedding_service
from app.services.onet_occupations import embed_occupations, fetch_onet_occupation_data_csv, infer_occupation, parse_occupations
from app.services.scoring_weights_store import load_active_weights
from app.services.taxonomy_loader import load_taxonomy_from_db

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
POSITIVE_PAIRS_PER_RESUME = 2
NEGATIVE_PAIRS_PER_RESUME = 2


def _extract_profiles(texts: dict[str, str], extractor, label: str) -> dict[str, object]:
    """Runs `extractor(text) -> Profile | None on failure`, skipping and
    reporting (not silently dropping) any text that fails our own
    parsers — real dataset text is messier than our hand-built fixtures."""
    profiles: dict[str, object] = {}
    failures = 0
    for i, (ref, text) in enumerate(texts.items(), 1):
        try:
            profiles[ref] = extractor(text)
        except DocumentParseError as exc:
            failures += 1
            print(f"  [{label}] skipping {ref} ({i}/{len(texts)}): {exc}")
        if i % 50 == 0:
            print(f"  [{label}] {i}/{len(texts)} processed, {failures} failures so far")
    print(f"  [{label}] done: {len(profiles)} extracted, {failures} failed")
    return profiles


def _extract_resume_profile(text: str) -> CandidateProfile:
    parsed = parse_text(insert_missing_header_breaks(text))
    return extract_candidate_profile(detect_sections(parsed))


def _extract_job_profile(text: str) -> JobProfile:
    parsed = parse_text(text)
    return extract_job_profile(detect_jd_sections(parsed))


def _occupation_query_text(profile: CandidateProfile | JobProfile) -> str | None:
    """docs/DATASET_STRATEGY.md §3 specs occupation inference "via most
    frequent job titles/skills" — skills was always the intended
    fallback, not new scope, but which signal to trust FIRST differs by
    side, found by actually running this against 15 real rows:

    - Resumes: experience[0].title, when present, is a clean, reliable
      signal — it was simply absent (None) more often than not, so
      skills is the fallback.
    - Jobs: title is a WRONG signal more often than an absent one — real
      postings routinely lead with a company-boilerplate paragraph
      ("Life at Capgemini...") rather than the role, which Phase 4's
      title heuristic (first line of the leading section) then confidently
      but incorrectly returns. A non-empty wrong string defeats an
      "only fall back if empty" check, so for jobs, required skills are
      tried FIRST and the title is the fallback, not the other way round.
    """
    if isinstance(profile, CandidateProfile):
        title = profile.experience[0].title if profile.experience else None
        if title:
            return title
        return ", ".join(profile.skills[:8]) if profile.skills else None

    required_skills = [s for item in profile.requirements for s in item.skills]
    if required_skills:
        return ", ".join(required_skills[:8])
    return profile.title


async def _upsert_label(session, row: DatasetRow, split: str) -> int:
    stmt = (
        pg_insert(TrainingLabel)
        .values(
            external_resume_ref=row.resume_ref,
            external_job_ref=row.job_ref,
            label=Decimal(str(round(row.label, 2))),
            label_source=row.label_source,
            dataset_split=split,
        )
        .on_conflict_do_nothing()
        .returning(TrainingLabel.id)
    )
    result = await session.execute(stmt)
    return 1 if result.scalar_one_or_none() is not None else 0


async def main(max_resumes: int | None, max_jobs: int | None, max_rule_based_pairs: int, seed: int) -> None:
    started = time.monotonic()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    print("Fetching cnamuangtoun/resume-job-description-fit...")
    pool = load_combined_pool()
    print(f"  {len(pool)} rows fetched")

    resume_texts, job_texts = dedupe_unique_texts(pool)
    if max_resumes:
        resume_texts = dict(list(resume_texts.items())[:max_resumes])
    if max_jobs:
        job_texts = dict(list(job_texts.items())[:max_jobs])
    pool = [row for row in pool if row.resume_ref in resume_texts and row.job_ref in job_texts]
    print(f"  {len(resume_texts)} unique resumes, {len(job_texts)} unique jobs (after any --max limits)")
    print(f"  {len(pool)} rows remain after limiting to those resumes/jobs")

    print("Extracting CandidateProfiles (spaCy — this is the slow step)...")
    resume_profiles = _extract_profiles(resume_texts, _extract_resume_profile, "resumes")
    print("Extracting JobProfiles...")
    job_profiles = _extract_profiles(job_texts, _extract_job_profile, "jobs")

    print("Fetching O*NET occupation taxonomy...")
    occupations = parse_occupations(fetch_onet_occupation_data_csv())
    embedding_service = get_embedding_service()
    occupation_embeddings = embed_occupations(occupations, embedding_service)
    print(f"  {len(occupations)} occupations loaded and embedded")

    print("Inferring occupation family per resume/job (title, falling back to skills)...")
    resume_major_group: dict[str, str | None] = {}
    for ref, profile in resume_profiles.items():
        query_text = _occupation_query_text(profile)
        match = infer_occupation(query_text, occupations, occupation_embeddings, embedding_service) if query_text else None
        resume_major_group[ref] = match.major_group if match else None

    job_major_group: dict[str, str | None] = {}
    for ref, profile in job_profiles.items():
        query_text = _occupation_query_text(profile)
        match = infer_occupation(query_text, occupations, occupation_embeddings, embedding_service) if query_text else None
        job_major_group[ref] = match.major_group if match else None

    resume_matched = sum(1 for g in resume_major_group.values() if g is not None)
    job_matched = sum(1 for g in job_major_group.values() if g is not None)
    print(f"  occupation inferred for {resume_matched}/{len(resume_major_group)} resumes, {job_matched}/{len(job_major_group)} jobs")

    # --- Save processed profiles (not the production resumes/jobs tables) ---
    (PROCESSED_DIR / "resume_profiles.json").write_text(
        json.dumps({ref: p.model_dump(mode="json") for ref, p in resume_profiles.items()}, indent=2)
    )
    (PROCESSED_DIR / "job_profiles.json").write_text(
        json.dumps({ref: p.model_dump(mode="json") for ref, p in job_profiles.items()}, indent=2)
    )
    print(f"  wrote parsed profiles to {PROCESSED_DIR}")

    # --- Label set 1: the dataset's own fit labels ---
    dataset_rows = [
        DatasetRow(resume_ref=row.resume_ref, job_ref=row.job_ref, label=row.label, label_source=CNAMUANGTOUN_LABEL_SOURCE)
        for row in pool
        if row.resume_ref in resume_profiles and row.job_ref in job_profiles
    ]
    print(f"Label set 1 (dataset:cnamuangtoun): {len(dataset_rows)} rows")

    # --- Label set 2: occupation-family positive/negative pairs ---
    occupation_rows: list[DatasetRow] = []
    resume_refs = list(resume_profiles.keys())
    job_refs = list(job_profiles.keys())
    for resume_ref in resume_refs:
        candidates = [(j, occupation_pair_label(resume_major_group[resume_ref], job_major_group[j])) for j in job_refs]
        positives = [j for j, lbl in candidates if lbl == 0.8]
        negatives = [j for j, lbl in candidates if lbl == 0.2]
        for job_ref in rng.sample(positives, min(POSITIVE_PAIRS_PER_RESUME, len(positives))):
            occupation_rows.append(DatasetRow(resume_ref, job_ref, 0.8, OCCUPATION_LABEL_SOURCE))
        for job_ref in rng.sample(negatives, min(NEGATIVE_PAIRS_PER_RESUME, len(negatives))):
            occupation_rows.append(DatasetRow(resume_ref, job_ref, 0.2, OCCUPATION_LABEL_SOURCE))
    print(f"Label set 2 (weak_supervision_occupation): {len(occupation_rows)} rows")

    # --- Label set 3: rule-based-score-derived tiers, on a sample ---
    print(f"Computing rule-based scores for up to {max_rule_based_pairs} sampled pairs...")
    async with SessionLocal() as session:
        taxonomy = await load_taxonomy_from_db(session)
        _, weights = await load_active_weights(session)

    candidate_pairs = list({(r.resume_ref, r.job_ref) for r in dataset_rows + occupation_rows})
    rng.shuffle(candidate_pairs)
    sampled_pairs = candidate_pairs[:max_rule_based_pairs]

    rule_based_rows: list[DatasetRow] = []
    for i, (resume_ref, job_ref) in enumerate(sampled_pairs, 1):
        features = compute_feature_vector(resume_profiles[resume_ref], job_profiles[job_ref], taxonomy, embedding_service)
        rule_based_score = score(features, weights)
        rule_based_rows.append(DatasetRow(resume_ref, job_ref, rule_based_tier_label(rule_based_score), RULE_BASED_LABEL_SOURCE))
        if i % 50 == 0:
            print(f"  {i}/{len(sampled_pairs)} pairs scored")
    print(f"Label set 3 (weak_supervision_rule_based): {len(rule_based_rows)} rows")

    # --- Grouped split across the combined row set ---
    # group_by="resume", not "both": verified the full bipartite (resume,
    # job) graph for this dataset is one single connected component
    # (resume degree up to 82, job degree up to 111 — see
    # data/README.md), which makes group_by="both" degenerate into one
    # split holding everything. Resume identity is the hard guarantee
    # that matters for this project (see grouped_split.py's docstring);
    # a job appearing across splits is a documented trade-off, not a bug.
    all_rows = dataset_rows + occupation_rows + rule_based_rows
    assignment = group_split(all_rows, seed=seed, group_by="resume")
    leakage = find_leakage(all_rows, assignment)
    if leakage["resumes"]:
        raise RuntimeError(f"Resume leakage detected, refusing to write labels: {leakage['resumes']}")
    print(
        f"Leakage check passed: no resume crosses a train/val/test boundary "
        f"({len(leakage['jobs'])} of {len(job_profiles)} jobs appear in more than one split — expected, see grouped_split.py)."
    )

    split_counts = {s: assignment.count(s) for s in ("train", "val", "test")}
    print(f"Split sizes: {split_counts}")

    print("Writing training_labels...")
    inserted = 0
    async with SessionLocal() as session:
        for row, split in zip(all_rows, assignment):
            inserted += await _upsert_label(session, row, split)
        await session.commit()
    print(f"Inserted {inserted} new training_labels rows (of {len(all_rows)} total, rest already existed)")

    elapsed = time.monotonic() - started
    print(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-resumes", type=int, default=None)
    parser.add_argument("--max-jobs", type=int, default=None)
    parser.add_argument("--max-rule-based-pairs", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    asyncio.run(main(args.max_resumes, args.max_jobs, args.max_rule_based_pairs, args.seed))
