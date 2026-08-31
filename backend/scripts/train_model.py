"""Train Phase 11's ranking models on Phase 10's data (docs/ROADMAP.md).

Lives in backend/scripts/, not the top-level scripts/ the roadmap names
literally — same bind-mount reasoning as build_dataset.py (needs
sentence-transformers for the feature matrix's semantic-similarity
columns, which only reliably works inside the backend Docker container).

Trains, in the order docs/ROADMAP.md's Phase 11 names them:
  1. Logistic Regression — baseline, classification on label >= 0.5.
  2. Random Forest       ) regression on the continuous [0,1] label —
  3. XGBoost             ) matches the rule-based scorer's own output
  4. LightGBM            ) shape, so predictions are directly comparable.
  5. LightGBM Ranker — the LTR objective (lambdarank), grouped by
     resume_ref so it directly optimizes "rank these jobs for this
     candidate" — the actual product task, not just a fit-score.

All five train on the combined train split across all three label
sources that exist today (dataset:cnamuangtoun, weak_supervision_occupation,
weak_supervision_rule_based) — docs/DATASET_STRATEGY.md §3 says no single
one of these is trusted alone as ground truth, but blended they're a
legitimate training signal; no source is used exclusively here, so that
constraint holds. evaluate.py is what reports metrics broken out per
source — training itself doesn't need that separation.

Run (inside the backend container):
    docker exec resume_matcher_backend python -m scripts.train_model
"""
import asyncio

from lightgbm import LGBMRanker, LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from xgboost import XGBRegressor

from app.db import SessionLocal
from app.ml.dataset_loader import FEATURE_NAMES, load_or_build_feature_matrix
from app.ml.model_registry import save_model
from app.services.embedding_service import get_embedding_service
from app.services.taxonomy_loader import load_taxonomy_from_db

RELEVANCE_THRESHOLD = 0.5
RANDOM_STATE = 42


def _binary_target(labels):
    return (labels >= RELEVANCE_THRESHOLD).astype(int)


def _relevance_grade(labels):
    # LightGBM's lambdarank objective wants small non-negative integer
    # relevance grades, not a continuous [0,1] score — 0..4 is the
    # conventional NDCG grading scale.
    return (labels * 4).round().clip(0, 4).astype(int)


async def main() -> None:
    async with SessionLocal() as session:
        taxonomy = await load_taxonomy_from_db(session)
        embedding_service = get_embedding_service()
        df = await load_or_build_feature_matrix(session, taxonomy, embedding_service)

    train_df = df[df.dataset_split == "train"].reset_index(drop=True)
    print(f"Training on {len(train_df)} rows (all label sources combined, per module docstring)")

    X_train = train_df[FEATURE_NAMES]
    y_train = train_df["label"].to_numpy()

    print("Training logistic_regression...")
    logreg_params = {"max_iter": 1000, "class_weight": "balanced"}
    logreg = LogisticRegression(**logreg_params).fit(X_train, _binary_target(y_train))
    save_model("logistic_regression", logreg, FEATURE_NAMES, logreg_params)

    print("Training random_forest...")
    rf_params = {"n_estimators": 300, "max_depth": 10, "random_state": RANDOM_STATE, "n_jobs": -1}
    rf = RandomForestRegressor(**rf_params).fit(X_train, y_train)
    save_model("random_forest", rf, FEATURE_NAMES, rf_params)

    print("Training xgboost...")
    xgb_params = {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05, "random_state": RANDOM_STATE, "n_jobs": -1}
    xgb = XGBRegressor(**xgb_params).fit(X_train, y_train)
    save_model("xgboost", xgb, FEATURE_NAMES, xgb_params)

    print("Training lightgbm...")
    lgbm_params = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
        "verbosity": -1,
    }
    lgbm = LGBMRegressor(**lgbm_params).fit(X_train, y_train)
    save_model("lightgbm", lgbm, FEATURE_NAMES, lgbm_params)

    print("Training lightgbm_ranker (LTR)...")
    # LightGBM's `group` param needs each query group's rows contiguous
    # in the exact order passed to fit() — sorting by resume_ref first is
    # what makes that true, not just a cosmetic ordering choice.
    ranker_train_df = train_df.sort_values("resume_ref").reset_index(drop=True)
    X_ranker = ranker_train_df[FEATURE_NAMES]
    relevance = _relevance_grade(ranker_train_df["label"].to_numpy())
    groups = ranker_train_df.groupby("resume_ref", sort=False).size().tolist()
    ranker_params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "random_state": RANDOM_STATE,
        "verbosity": -1,
    }
    ranker = LGBMRanker(**ranker_params).fit(X_ranker, relevance, group=groups)
    save_model("lightgbm_ranker", ranker, FEATURE_NAMES, ranker_params)

    print("Done — 5 models saved to backend/data/models/. Run evaluation.evaluate for metrics.")


if __name__ == "__main__":
    asyncio.run(main())
