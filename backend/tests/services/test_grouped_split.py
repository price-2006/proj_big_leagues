"""Phase 10 test procedure per docs/ROADMAP.md: build_dataset.py produces
a train/val/test split with no resume or job text leaking across splits
— an automated leakage-check assertion, not a manual eyeball.
"""
from app.services.dataset_sources.grouped_split import DatasetRow, find_leakage, group_split


def _row(resume_ref: str, job_ref: str, label: float = 0.5) -> DatasetRow:
    return DatasetRow(resume_ref=resume_ref, job_ref=job_ref, label=label, label_source="test")


def test_no_leakage_on_a_realistic_many_to_many_dataset():
    """Mirrors the real shape: some resumes paired with multiple jobs,
    some jobs paired with multiple resumes (the cnamuangtoun dataset's
    8,000 rows behind 643 resumes / 351 jobs)."""
    rows = []
    for resume_i in range(50):
        for job_i in range(3):
            rows.append(_row(f"resume-{resume_i}", f"job-{(resume_i * 3 + job_i) % 40}"))

    assignment = group_split(rows, seed=1)
    leakage = find_leakage(rows, assignment)
    assert leakage == {"resumes": {}, "jobs": {}}


def test_transitive_chain_stays_in_one_split():
    """resume A -- job X -- resume B -- job Y: A and B never directly
    share a job, but are connected through X, so they (and Y) must all
    land in the same split — this is exactly what union-find catches
    that a naive 'group by resume only' or 'group by job only' split
    would miss."""
    rows = [
        _row("resume-A", "job-X"),
        _row("resume-B", "job-X"),
        _row("resume-B", "job-Y"),
    ]
    assignment = group_split(rows, seed=1)
    assert len(set(assignment)) == 1  # all three rows in the same split
    assert find_leakage(rows, assignment) == {"resumes": {}, "jobs": {}}


def test_disjoint_components_can_land_in_different_splits():
    rows = [_row(f"resume-{i}", f"job-{i}") for i in range(30)]  # each pair is its own component
    assignment = group_split(rows, train_frac=0.5, val_frac=0.25, seed=1)
    assert len(set(assignment)) > 1  # actually spread across splits, not dumped in one
    assert find_leakage(rows, assignment) == {"resumes": {}, "jobs": {}}


def test_split_proportions_are_approximately_correct_for_many_small_components():
    rows = [_row(f"resume-{i}", f"job-{i}") for i in range(300)]
    assignment = group_split(rows, train_frac=0.7, val_frac=0.15, seed=7)
    counts = {split: assignment.count(split) for split in ("train", "val", "test")}
    assert counts["train"] / len(rows) == 0.7  # exact here: 300 singleton components divide evenly
    assert counts["val"] / len(rows) == 0.15
    assert counts["test"] / len(rows) == 0.15


def test_every_row_gets_assigned_exactly_once():
    rows = [_row(f"resume-{i}", f"job-{i % 10}") for i in range(75)]
    assignment = group_split(rows, seed=3)
    assert len(assignment) == len(rows)
    assert all(s in ("train", "val", "test") for s in assignment)


def test_same_seed_is_reproducible():
    rows = [_row(f"resume-{i}", f"job-{i % 15}") for i in range(60)]
    assert group_split(rows, seed=42) == group_split(rows, seed=42)


def test_find_leakage_detects_an_intentionally_broken_split():
    """Sanity check on the detector itself: feed it an assignment that
    puts the two halves of one component in different splits."""
    rows = [_row("resume-A", "job-X"), _row("resume-A", "job-Y")]
    broken_assignment = ["train", "test"]  # same resume in both splits
    leakage = find_leakage(rows, broken_assignment)
    assert "resume-A" in leakage["resumes"]
    assert leakage["resumes"]["resume-A"] == {"train", "test"}


def _densely_connected_rows(n_resumes: int = 60, n_jobs: int = 40, edges_per_resume: int = 15) -> list[DatasetRow]:
    """Mirrors the real cnamuangtoun shape closely enough to reproduce its
    behavior: each resume paired with many jobs, densely enough that the
    bipartite graph collapses into one giant connected component — a
    real, verified property of the real dataset (see data/README.md),
    not a hypothetical worst case invented for this test."""
    import random as _random

    rng = _random.Random(0)
    rows = []
    for i in range(n_resumes):
        for job_i in rng.sample(range(n_jobs), edges_per_resume):
            rows.append(_row(f"resume-{i}", f"job-{job_i}"))
    return rows


def test_group_by_both_degenerates_on_a_densely_connected_graph():
    """Regression test for a real bug found by actually running the full
    dataset build: group_by="both" on the real cnamuangtoun data put
    every one of 10,081 rows in train and left val/test empty, because
    the entire 643-resume/351-job graph is one connected component
    (verified directly, not assumed). This reproduces that failure mode
    on a smaller synthetic graph with the same dense-pairing shape."""
    rows = _densely_connected_rows()
    assignment = group_split(rows, seed=1, group_by="both")
    counts = {s: assignment.count(s) for s in ("train", "val", "test")}
    assert counts["val"] == 0 and counts["test"] == 0  # documents the degenerate outcome, not desired behavior


def test_group_by_resume_still_splits_the_same_densely_connected_graph():
    """The fix: group_by="resume" ignores job-side connectivity for
    grouping, so the same dense graph above splits into three real,
    non-empty partitions — no resume crosses a boundary (the hard
    guarantee), while jobs may legitimately appear in more than one
    split (the documented, accepted trade-off — see module docstring)."""
    rows = _densely_connected_rows()
    assignment = group_split(rows, seed=1, group_by="resume")
    counts = {s: assignment.count(s) for s in ("train", "val", "test")}
    assert counts["train"] > 0 and counts["val"] > 0 and counts["test"] > 0

    leakage = find_leakage(rows, assignment)
    assert leakage["resumes"] == {}  # the actual guarantee this mode makes
    assert leakage["jobs"] != {}  # the expected, accepted trade-off — not a bug
