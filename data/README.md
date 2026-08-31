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

## Model training and evaluation (Phase 11)

```bash
docker exec resume_matcher_backend python -m scripts.train_model
docker exec resume_matcher_backend python -m evaluation.evaluate --split test   # or --split val
```

Both live under `backend/` (`scripts/train_model.py`, `evaluation/evaluate.py`)
rather than the repo-root `scripts/`/`evaluation/` the roadmap names
literally — same bind-mount reasoning as `build_dataset.py`: they need
`sentence-transformers`, only installed in the backend image, and that
image only bind-mounts `./backend`. `train_model.py` builds a feature
matrix (10 features + the embedding-cosine baseline, per pair) from
`training_labels` + the parsed profiles, caches it to
`backend/data/processed/feature_matrix.csv` so `evaluate.py` doesn't
recompute it, and trains five models to `backend/data/models/`:
Logistic Regression (baseline), Random Forest, XGBoost, LightGBM (all
four regressing on the continuous label), and a LightGBM LTR ranker
(`lambdarank` objective, grouped by resume — directly optimizing "rank
these jobs for this candidate," the real product task). `evaluate.py`
scores the held-out split with the rule-based scorer, a "plain"
whole-document embedding-cosine-similarity baseline, and all five
trained models; logs every run to MLflow (SQLite backend — see below)
and mirrors it into the `experiments` table.

### Two real bugs found by actually running this, both fixed and reverified

1. **`data/processed/*.json` was being written outside the Docker bind
   mount.** `build_dataset.py`'s `PROCESSED_DIR` resolved three parents
   up from `__file__`, landing at the container filesystem root's own
   `/data/processed` — invisible on the host and gone on any container
   recreation, which is exactly what happened between Phase 10 and
   Phase 11 (rebuilding the image for Phase 11's new dependencies wiped
   it). Fixed to resolve to `backend/data/processed/`, which the
   `./backend:/app` mount actually exposes; re-ran `build_dataset.py` to
   regenerate the profiles there.
2. **`training_labels` had no unique constraint**, so `_upsert_label`'s
   `ON CONFLICT DO NOTHING` had nothing to conflict on (`id` is a fresh
   `uuid4()` every insert) — every re-run of `build_dataset.py` silently
   doubled the table (confirmed live: 10,081 -> 20,162 rows after one
   extra run). A second, related bug compounded it: `candidate_pairs`
   for the rule-based label sample was built via `list({...})` over a
   Python `set`, whose iteration order depends on per-process hash
   randomization, not just `--seed` — so `--seed 42` produced a
   *different* rule-based sample on every process invocation, silently
   breaking the reproducibility `ROADMAP.md`'s Phase 10 "Test" line
   requires. Fixed both: added a real unique constraint on
   `(external_resume_ref, external_job_ref, label_source)`
   (`alembic/versions/0008_training_labels_unique.py`, which also
   de-duplicates the corrupted rows already on disk), pointed
   `on_conflict_do_nothing` at it explicitly, and changed `list({...})`
   to `sorted({...})` before shuffling. Reverified by actually re-running
   `build_dataset.py` twice with the same seed: identical split sizes
   both times (`{'train': 7062, 'val': 1532, 'test': 1487}`) and the
   second run inserted 0 new rows — true reproducibility and idempotency,
   not asserted, checked.
3. **Smaller:** MLflow 3.x's plain filesystem tracking store (`./mlruns`)
   is in maintenance mode and refuses new writes. `ARCHITECTURE.md` §4/§14
   sanctions "local file/SQLite backend to start" either way, so
   `mlflow_tracking_uri` now defaults to `sqlite:///mlflow.db` (also
   MLflow's own currently-recommended local option) instead.

### Real numbers from the test split (1,484 rows: 1,133 `dataset:cnamuangtoun` /
### 284 `weak_supervision_occupation` / 67 `weak_supervision_rule_based`)

Precision/Recall/F1/ROC-AUC use `label >= 0.5` as ground truth; NDCG@5/MRR
are grouped by resume (ranking "jobs for this candidate") and averaged
over groups with 2+ items. No `human_annotated` gold set exists yet
(`DATASET_STRATEGY.md` §3: "recommended, not yet collected" — "the one
label source trusted enough to appear in the headline `evaluate.py`
output"), so none of the numbers below is asserted as *the* headline
number — they're reported per source, honestly, as that section requires.

**`dataset:cnamuangtoun` (n=1133):**

| approach | precision | recall | f1 | roc_auc | ndcg@5 | mrr |
|---|---|---|---|---|---|---|
| rule_based | 0.000 | 0.000 | 0.000 | 0.491 | 0.447 | 0.261 |
| embedding_cosine | 0.705 | 0.161 | 0.263 | 0.618 | 0.491 | 0.583 |
| logistic_regression | 0.484 | 0.102 | 0.169 | 0.488 | 0.446 | 0.465 |
| random_forest | 0.615 | 0.014 | 0.027 | 0.511 | 0.479 | 0.451 |
| xgboost | 0.767 | 0.040 | 0.076 | 0.508 | 0.471 | 0.450 |
| lightgbm | 0.722 | 0.023 | 0.044 | 0.511 | 0.479 | 0.455 |
| lightgbm_ranker | 0.571 | 0.069 | 0.124 | 0.511 | 0.474 | 0.422 |

**`weak_supervision_occupation` (n=284):**

| approach | precision | recall | f1 | roc_auc | ndcg@5 | mrr |
|---|---|---|---|---|---|---|
| rule_based | 0.000 | 0.000 | 0.000 | 0.503 | 0.865 | 0.932 |
| embedding_cosine | 0.795 | 0.228 | 0.354 | 0.672 | 0.915 | 0.793 |
| logistic_regression | 0.625 | 0.110 | 0.188 | 0.544 | 0.875 | 0.905 |
| random_forest | 0.000 | 0.000 | 0.000 | 0.540 | 0.876 | 0.926 |
| xgboost | 0.000 | 0.000 | 0.000 | 0.529 | 0.870 | 0.905 |
| lightgbm | 0.000 | 0.000 | 0.000 | 0.541 | 0.876 | 0.926 |
| lightgbm_ranker | 0.480 | 0.978 | 0.644 | 0.516 | 0.869 | 0.926 |

**`weak_supervision_rule_based` (n=67):** every approach reports
precision/recall/f1 = 0.000, roc_auc = None, ndcg@5 = 1.000, mrr = 0.000
— identically, across the board. Reported as-is rather than dropped:
this is a small-sample artifact (67 rows, further split into per-resume
ranking groups), not a real signal — this slice of the test split
happened to land only on the low tier of `rule_based_tier_label`'s
three-way split, so `label >= 0.5` is `False` for every row here
(`roc_auc` correctly reports `None` — only one class present to score
against), and no group has a "relevant" item for MRR to find. Read this
row as "not enough data in this slice to say anything," not as "every
model fails identically here."

### Honest reading of the above — nothing here is smoothed over

- **The rule-based scorer's raw scores almost never cross the 0.5
  classification threshold** (precision/recall/f1 pinned at 0.000 on
  every source) despite genuinely reasonable ranking quality on the
  first two sources (NDCG@5 0.447/0.865, MRR 0.261/0.932) — its weighted
  formula (`DEFAULT_WEIGHTS`, `app/ml/rule_based_scorer.py`) rarely
  produces a raw output above ~0.5 even for comparatively strong matches,
  a calibration property of the hand-designed v1 formula, not a Phase 11
  bug. It still *ranks* reasonably; it just isn't well-calibrated as a
  0/1 classifier at this specific threshold.
- **The "plain" embedding-cosine baseline is competitive with, or ahead
  of, every trained model** on precision/recall/f1/ROC-AUC for both
  `dataset:cnamuangtoun` and `weak_supervision_occupation`. This is
  reported plainly rather than reframed: on this data, at this scope
  (~7k train rows, 10 features, no hyperparameter search beyond the
  documented fixed configs in `train_model.py`), the trained models
  haven't yet clearly beaten the simplest possible whole-document
  similarity score. A larger/cleaner training set and real
  hyperparameter tuning are the obvious next levers, not claimed here as
  already pulled.
- **`lightgbm_ranker` (the LTR model) stands out on
  `weak_supervision_occupation` recall/F1** (0.978 / 0.644, well above
  every other model) — consistent with it directly optimizing a ranking
  loss instead of a pointwise regression target, though its precision
  (0.480) shows that comes with predicting "relevant" much more often
  overall on this source.
- None of these numbers should be read as "the model works" or "the
  model doesn't work" in an absolute sense — per `DATASET_STRATEGY.md`
  §3, every source above is weak/auxiliary supervision, not ground
  truth. A trustworthy headline number needs the `human_annotated` gold
  set this section (and Phase 10's) still flags as not yet collected.

## Skill taxonomy sources (Phase 5)

Seeded by `backend/scripts/seed_skills.py` directly into Postgres — not staged as files under `raw/`, since each source is small enough to fetch and load in one step rather than needing a separate download/preprocess split.

| Source | Accessed | Version | License | Status |
|---|---|---|---|---|
| O*NET Database, U.S. Dept. of Labor / Employment and Training Administration — `dl_files/database/db_31_0_csv/software_skills.csv` | 2026-08-29 | 31.0 | CC BY 4.0, confirmed on `onetcenter.org/database.html` | **Integrated.** Only rows flagged `Hot Technology = Y` (~176 of ~7,700 unique entries) are kept — the rest is mostly low-relevance occupational software (e.g. "Blackbaud The Raiser's Edge") not worth seeding into a tech-resume-focused taxonomy. Attribution: "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration." |
| ESCO (EU Skills/Competences/Qualifications/Occupations) — `esco.ec.europa.eu` | 2026-08-29 | v1.2.1 | Stated "free of charge"; no explicit reuse/redistribution license found on the download page | **Not integrated.** ESCO's CSV download is gated behind an email-registration workflow (select filters → privacy statement → email → link sent), which isn't something a script can complete unattended. A direct RDF download exists for v1.2.0 but not CSV. Left as a documented gap rather than skipped silently or faked — pick up the emailed CSV link manually and feed it through a `load_esco_skills(csv_path)` loader (not yet written) if/when this is worth completing. |
| Internal curated set — `backend/app/services/skill_seed_data.py` | — | — | Original, part of this repo | **Integrated.** ~60 skills with explicit categories, alias variants, and the 5 disambiguation pairs (Java/JavaScript, React/React Native, Angular/AngularJS, PyTorch/TensorFlow, C++/C#) that a flat gazetteer list can't express. |

Re-run `python -m scripts.seed_skills` (from `backend/`, Postgres up, migrations applied) any time after editing the internal seed list — it's idempotent, so already-seeded rows are skipped.
