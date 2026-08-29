# Data directory

Raw and processed dataset files are **not committed to this repository** — see `docs/DATASET_STRATEGY.md` for the full rationale (per-source licensing, size, and reproducibility).

Once `scripts/build_dataset.py` exists (Phase 10), each dataset used there will be documented here the same way. `raw/` holds untouched downloads; `processed/` holds the output of the preprocessing pipeline (deduplicated, parsed through the product's own parsers, split into train/val/test — see `DATASET_STRATEGY.md` §4-5). Both are gitignored.

## Skill taxonomy sources (Phase 5)

Seeded by `backend/scripts/seed_skills.py` directly into Postgres — not staged as files under `raw/`, since each source is small enough to fetch and load in one step rather than needing a separate download/preprocess split.

| Source | Accessed | Version | License | Status |
|---|---|---|---|---|
| O*NET Database, U.S. Dept. of Labor / Employment and Training Administration — `dl_files/database/db_31_0_csv/software_skills.csv` | 2026-08-29 | 31.0 | CC BY 4.0, confirmed on `onetcenter.org/database.html` | **Integrated.** Only rows flagged `Hot Technology = Y` (~176 of ~7,700 unique entries) are kept — the rest is mostly low-relevance occupational software (e.g. "Blackbaud The Raiser's Edge") not worth seeding into a tech-resume-focused taxonomy. Attribution: "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration." |
| ESCO (EU Skills/Competences/Qualifications/Occupations) — `esco.ec.europa.eu` | 2026-08-29 | v1.2.1 | Stated "free of charge"; no explicit reuse/redistribution license found on the download page | **Not integrated.** ESCO's CSV download is gated behind an email-registration workflow (select filters → privacy statement → email → link sent), which isn't something a script can complete unattended. A direct RDF download exists for v1.2.0 but not CSV. Left as a documented gap rather than skipped silently or faked — pick up the emailed CSV link manually and feed it through a `load_esco_skills(csv_path)` loader (not yet written) if/when this is worth completing. |
| Internal curated set — `backend/app/services/skill_seed_data.py` | — | — | Original, part of this repo | **Integrated.** ~60 skills with explicit categories, alias variants, and the 5 disambiguation pairs (Java/JavaScript, React/React Native, Angular/AngularJS, PyTorch/TensorFlow, C++/C#) that a flat gazetteer list can't express. |

Re-run `python -m scripts.seed_skills` (from `backend/`, Postgres up, migrations applied) any time after editing the internal seed list — it's idempotent, so already-seeded rows are skipped.
