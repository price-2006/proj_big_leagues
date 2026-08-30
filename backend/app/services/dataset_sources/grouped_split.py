"""Group-aware train/val/test split (Phase 10, docs/DATASET_STRATEGY.md §5).

Two grouping modes, because the real data forced a real decision here,
not a hypothetical one:

- `group_by="both"`: no resume text AND no job text appears in more than
  one split — rows sharing a resume OR a job, directly or transitively
  through a chain of shared pairings, form one connected component via
  union-find and must land together. This is DATASET_STRATEGY.md §5's
  literal spec, and it's what this module originally implemented.
- `group_by="resume"`: only resume identity is a hard constraint; a job
  may appear paired with different resumes across splits.

Why both exist: checked the real cnamuangtoun bipartite graph (643
resumes, 351 jobs, 8000 edges, resume degree up to 82, job degree up to
111) before finalizing this — it forms exactly ONE connected component.
`group_by="both"` on that data doesn't produce three splits; it produces
one split holding everything and two empty ones (verified by actually
running it, not predicted). The dataset's own construction — a limited
resume/job pool densely cross-paired to generate 8,000 labeled examples —
makes the literal "no resume or job crosses a boundary" spec
mathematically unsatisfiable for a non-trivial 3-way split of this
specific source. `group_by="resume"` is the fallback: resume identity is
the axis that matters most for this project (a candidate uploads one
resume and is matched against many jobs — the evaluation question is
"does the model generalize to an unseen candidate," not "an unseen job
posting," and job postings cluster tightly around common titles/duties
regardless). build_dataset.py uses `group_by="resume"` for exactly this
reason, and find_leakage's job-side report on that split is expected to
show overlap — that's not a bug, it's the documented trade-off.
"""
import random
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DatasetRow:
    resume_ref: str  # stable id/hash of the resume text
    job_ref: str  # stable id/hash of the job text
    label: float
    label_source: str


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b


def _components_both(rows: list[DatasetRow]) -> dict[str, list[int]]:
    uf = _UnionFind()
    for row in rows:
        uf.union(f"r:{row.resume_ref}", f"j:{row.job_ref}")

    components: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        root = uf.find(f"r:{row.resume_ref}")
        components.setdefault(root, []).append(i)
    return components


def _components_resume_only(rows: list[DatasetRow]) -> dict[str, list[int]]:
    components: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        components.setdefault(row.resume_ref, []).append(i)
    return components


def group_split(
    rows: list[DatasetRow],
    train_frac: float = 0.7,
    val_frac: float = 0.15,
    seed: int = 42,
    group_by: Literal["both", "resume"] = "both",
) -> list[str]:
    """Returns a list of 'train'/'val'/'test' labels parallel to `rows`.
    Components are assigned to the first split with room left (greedy
    bin-packing) in a seeded-random component order — the resulting
    proportions approximate train_frac/val_frac/(1 - both), not hit them
    exactly, since a component can't be split across boundaries. See the
    module docstring for when a "component" is too large for this to work
    at all, and why `group_by="resume"` exists.
    """
    components = _components_both(rows) if group_by == "both" else _components_resume_only(rows)

    component_keys = list(components.keys())
    random.Random(seed).shuffle(component_keys)

    total = len(rows)
    train_target = int(total * train_frac)
    val_target = int(total * val_frac)

    assignment: list[str | None] = [None] * total
    train_count = val_count = 0
    for key in component_keys:
        indices = components[key]
        if train_count < train_target:
            split = "train"
            train_count += len(indices)
        elif val_count < val_target:
            split = "val"
            val_count += len(indices)
        else:
            split = "test"
        for i in indices:
            assignment[i] = split

    assert all(s is not None for s in assignment)  # every row visited exactly once, by construction
    return assignment  # type: ignore[return-value]


def find_leakage(rows: list[DatasetRow], assignment: list[str]) -> dict[str, dict[str, set[str]]]:
    """Returns {'resumes': {ref: {splits}}, 'jobs': {ref: {splits}}} for
    any ref that landed in more than one split — empty dicts mean clean
    on that axis. Useful as a report regardless of which group_by mode
    produced `assignment`: for group_by="resume", the "jobs" half is
    expected to show overlap (that's the documented trade-off, not a
    bug) — only the "resumes" half is the actual guarantee to check."""
    resume_splits: dict[str, set[str]] = {}
    job_splits: dict[str, set[str]] = {}
    for row, split in zip(rows, assignment):
        resume_splits.setdefault(row.resume_ref, set()).add(split)
        job_splits.setdefault(row.job_ref, set()).add(split)

    return {
        "resumes": {ref: splits for ref, splits in resume_splits.items() if len(splits) > 1},
        "jobs": {ref: splits for ref, splits in job_splits.items() if len(splits) > 1},
    }
