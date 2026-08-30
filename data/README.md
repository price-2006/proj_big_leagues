# Data directory

Raw and processed dataset files are **not committed to this repository** — see `docs/DATASET_STRATEGY.md` for the full rationale (per-source licensing, size, and reproducibility).

`raw/` holds untouched downloads; `processed/` holds the output of the preprocessing pipeline (deduplicated, parsed through the product's own parsers, split into train/val/test — see `DATASET_STRATEGY.md` §4-5). Both are gitignored.

## Training data (Phase 10)

Built by `backend/scripts/build_dataset.py` — lives there rather than the
top-level `scripts/` this file's own directory implies, because it needs
spaCy (resume extraction), which only works reliably inside the backend
Docker container on this machine, and that container only bind-mounts
`./backend`, not the repo root:

```bash
docker exec resume_matcher_backend python -m scripts.build_dataset
# smaller test run:
docker exec resume_matcher_backend python -m scripts.build_dataset --max-resumes 15 --max-jobs 10 --max-rule-based-pairs 20
```

| Source | Accessed | Rows | License | Status |
|---|---|---|---|---|
| `cnamuangtoun/resume-job-description-fit` (Hugging Face) — `train.csv` + `test.csv` | 2026-08-30 | 8,000 (6,241 + 1,759), 643 unique resumes, 351 unique jobs | No license published on the dataset page — confirm before any redistribution/commercial use | **Integrated.** Public, ungated (confirmed via the HF API: `gated: false, private: false`), no account needed. |
| O*NET Occupation Data — `dl_files/database/db_31_0_csv/occupation_data.csv` | 2026-08-30 | 1,016 occupations, all SOC major groups | CC BY 4.0 (same source as Phase 5's skill data) | **Integrated.** Broader coverage than Phase 5's Hot-Technology subset — needed for a dataset spanning sales, construction, and engineering roles, not just tech. |

### The dataset's own train/test split leaks — verified, not assumed

`DATASET_STRATEGY.md` §2.1 warned a row-level split would leak given the
642×280 duplication behind 8,000 rows. Checked directly against the real
files before writing any split logic: **476 of the 477 unique resumes in
`test.csv` also appear in `train.csv`** (0 job overlap). The dataset's own
train/test boundary is discarded entirely — `build_dataset.py` concatenates
both files into one pool and re-splits with
`app/services/dataset_sources/grouped_split.py` (union-find over shared
resume/job text, so even indirect leakage through a chain of shared
pairings is caught), verified by an automated leakage-check assertion
after every run, not a manual eyeball.

### The full resume/job graph is one giant connected component — found by actually running the split, not predicted

`DATASET_STRATEGY.md` §5's literal spec — group by shared resume *or* job
text (`grouped_split.py`'s `group_by="both"` mode) — was the first thing
tried, and it broke on the real data: a full run over all 643 resumes and
351 jobs produced `{'train': 10081, 'val': 0, 'test': 0}`. Every row
landed in train; val and test were empty. Root cause, confirmed directly
by union-find over the real pairing graph (before any weak-supervision
augmentation): it's already **one single connected component** — 643
resumes + 351 jobs = 994 nodes, all reachable from each other through
shared pairings (resume degree up to 82, job degree up to 111; means
12.44 / 22.79). The dataset's own construction — a limited resume/job
pool densely cross-paired to manufacture 8,000 labeled rows — makes a
non-trivial 3-way "no resume or job crosses a boundary" split
mathematically impossible for this specific source, not a bug in the
splitting code.

Fix: `grouped_split.py` gained a `group_by: Literal["both", "resume"]`
parameter. `build_dataset.py` uses `group_by="resume"` — only resume
identity is a hard constraint (no resume's rows cross a split boundary);
a job may legitimately appear paired with different resumes across
splits. This is a deliberate trade-off, not a workaround: resume identity
is the axis that matters for this project (a candidate uploads one
resume and is matched against many jobs — the evaluation question is
"does the model generalize to an unseen candidate," not "an unseen job
posting," and job postings cluster tightly around a much smaller set of
common titles/duties regardless). The automated leakage check only fails
the run on resume-side leakage; job-side overlap is logged, not treated
as an error. Regression tests for both the degenerate `"both"` behavior
and the working `"resume"` behavior live in
`backend/tests/services/test_grouped_split.py`.

### Real-world text quality: two genuine extraction gaps found, one fixed

Running actual extraction against real dataset text (not just our own
hand-built fixtures) surfaced two distinct problems:

1. **Fixed.** `resume_text` has section headers glued directly to content
   with no separator — `"SummaryHighly motivated Sales Associate..."`,
   `"ExperienceAccountant,08/2014-05/2015..."` — a lost-line-break
   artifact from whatever process extracted this dataset's text (most
   likely PDF-to-text), confirmed consistent across every sample row
   checked. `app/services/dataset_sources/text_cleanup.py` inserts the
   missing breaks before known header keywords — scoped to the dataset
   ingestion pipeline only, never touching the parsers real user uploads
   go through.
2. **Documented, not fixed.** A meaningful fraction of `job_description_text`
   values are unstructured narrative prose with no labeled
   Requirements/Responsibilities section at all — company-boilerplate
   paragraphs, or free-flowing role descriptions. This isn't a missing-
   line-break artifact fixable with a targeted regex; parsing arbitrary
   narrative text into a required/preferred requirement list is an
   open-ended NLP problem, well beyond this phase's proportionate scope.
   Effect: lower requirement-skill extraction yield on the job side,
   which lowers occupation-family weak-supervision yield for those rows
   (see below) — a real, visible characteristic of this run's output, not
   a hidden failure. `job_information_extraction.py` itself is unchanged.

### Weak supervision — three label sources, tagged separately, never blended

Per `DATASET_STRATEGY.md` §3, written to `training_labels` with distinct
`label_source` values:

- `dataset:cnamuangtoun` — the dataset's own 3-way fit label (`No Fit` /
  `Potential Fit` / `Good Fit`), mapped to 0.0 / 0.5 / 1.0. Provenance is
  undocumented by the dataset itself — auxiliary signal, not headline
  ground truth.
- `weak_supervision_occupation` — resume paired with a job in the same
  (positive, 0.8) or a different (negative, 0.2) O*NET major group.
  Occupation is inferred by embedding similarity against all 1,016 O*NET
  titles (`app/services/onet_occupations.py`) from title-or-skills text —
  an earlier character/token-similarity version of this matcher produced
  confidently wrong matches on real titles ("Software Engineer" ->
  "Sales Engineers", "Sales Associate" -> "Surgical Assistants"); switching
  to embeddings fixed both (verified against the real, full occupation
  list before being locked in as a regression test). Distant supervision,
  not ground truth — DATASET_STRATEGY.md §3 is explicit about that.
- `weak_supervision_rule_based` — Phase 7's real rule-based scorer, run
  on a sampled subset of pairs (not the full ~226k resume×job
  cross-product — not a proportionate amount of embedding compute for a
  portfolio-scale project), discretized into a coarse tier. Not eligible
  as a sole/headline signal — it's the same scorer Phase 11 is meant to
  improve on.

The recommended fourth source, a small hand-annotated gold set
(`label_source = 'human_annotated'`), is `DATASET_STRATEGY.md` §3's own
"recommended, not yet collected" — still not collected; Phase 11's
headline evaluation numbers will need it before they can be reported
honestly, per that section.

## Skill taxonomy sources (Phase 5)

Seeded by `backend/scripts/seed_skills.py` directly into Postgres — not staged as files under `raw/`, since each source is small enough to fetch and load in one step rather than needing a separate download/preprocess split.

| Source | Accessed | Version | License | Status |
|---|---|---|---|---|
| O*NET Database, U.S. Dept. of Labor / Employment and Training Administration — `dl_files/database/db_31_0_csv/software_skills.csv` | 2026-08-29 | 31.0 | CC BY 4.0, confirmed on `onetcenter.org/database.html` | **Integrated.** Only rows flagged `Hot Technology = Y` (~176 of ~7,700 unique entries) are kept — the rest is mostly low-relevance occupational software (e.g. "Blackbaud The Raiser's Edge") not worth seeding into a tech-resume-focused taxonomy. Attribution: "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration." |
| ESCO (EU Skills/Competences/Qualifications/Occupations) — `esco.ec.europa.eu` | 2026-08-29 | v1.2.1 | Stated "free of charge"; no explicit reuse/redistribution license found on the download page | **Not integrated.** ESCO's CSV download is gated behind an email-registration workflow (select filters → privacy statement → email → link sent), which isn't something a script can complete unattended. A direct RDF download exists for v1.2.0 but not CSV. Left as a documented gap rather than skipped silently or faked — pick up the emailed CSV link manually and feed it through a `load_esco_skills(csv_path)` loader (not yet written) if/when this is worth completing. |
| Internal curated set — `backend/app/services/skill_seed_data.py` | — | — | Original, part of this repo | **Integrated.** ~60 skills with explicit categories, alias variants, and the 5 disambiguation pairs (Java/JavaScript, React/React Native, Angular/AngularJS, PyTorch/TensorFlow, C++/C#) that a flat gazetteer list can't express. |

Re-run `python -m scripts.seed_skills` (from `backend/`, Postgres up, migrations applied) any time after editing the internal seed list — it's idempotent, so already-seeded rows are skipped.
