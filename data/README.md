# Data directory

Raw and processed dataset files are **not committed to this repository** — see `docs/DATASET_STRATEGY.md` for the full rationale (per-source licensing, size, and reproducibility).

Once `scripts/build_dataset.py` exists (Phase 10), each dataset used will be documented here with: source URL, version/date accessed, license, and the local download command. `raw/` holds untouched downloads; `processed/` holds the output of the preprocessing pipeline (deduplicated, parsed through the product's own parsers, split into train/val/test — see `DATASET_STRATEGY.md` §4-5). Both are gitignored.
