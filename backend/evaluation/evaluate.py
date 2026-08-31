"""evaluate.py — Phase 11 (docs/ROADMAP.md, docs/ARCHITECTURE.md §13).

Scores a held-out split (test by default) with:
  - rule_based        — app/ml/rule_based_scorer.py's real v1 formula.
  - embedding_cosine   — the "plain" whole-document cosine-similarity
                          baseline (app/ml/dataset_loader.py's
                          precomputed column) — no ML, no structured
                          features, the simplest thing that could work.
  - every model train_model.py saved to backend/data/models/
    (logistic_regression, random_forest, xgboost, lightgbm, lightgbm_ranker).

For each, reports Precision/Recall/F1/ROC-AUC (classification framing,
label >= 0.5 as ground truth) and NDCG@5/MRR (ranking framing, grouped by
resume_ref — "rank jobs for this candidate" is the actual product task)
— broken out PER label_source, never blended into one number
(docs/DATASET_STRATEGY.md §3: "a model's headline NDCG@5 is never
computed by mixing weak and real labels into one number").

No `human_annotated` gold-set rows exist yet — DATASET_STRATEGY.md §3
calls that source "recommended, not yet collected" and is explicit that
it's "the one label source trusted enough to appear in the headline
evaluate.py output; everything else trains, this alone validates." This
run reports metrics for the three label sources that do exist and says
so plainly below, rather than asserting one headline number the dataset
strategy itself says isn't trustworthy yet (ARCHITECTURE.md §13's
no-fabricated-metric rule).

Every run logs to MLflow (local file backend, see app/config.py's
mlflow_tracking_uri) and mirrors into the `experiments` table.

Lives in backend/evaluation/, not the repo-root evaluation/ the roadmap
names literally — same bind-mount reasoning as build_dataset.py/
train_model.py (needs sentence-transformers, only installed in the
backend image, and that image only bind-mounts ./backend).

Run (inside the backend container):
    docker exec resume_matcher_backend python -m evaluation.evaluate [--split test]
"""
import argparse
import asyncio

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from app.db import SessionLocal
from app.ml.dataset_loader import EMBEDDING_COSINE_BASELINE_COLUMN, FEATURE_NAMES, load_or_build_feature_matrix
from app.ml.experiment_logger import log_experiment
from app.ml.metrics import mrr_grouped, ndcg_at_k_grouped
from app.ml.model_registry import load_model
from app.ml.rule_based_scorer import DEFAULT_WEIGHTS
from app.ml.rule_based_scorer import score as rule_based_score
from app.schemas.match_features import FeatureVector
from app.services.embedding_service import get_embedding_service
from app.services.taxonomy_loader import load_taxonomy_from_db

# Bumped manually if build_dataset.py's pipeline changes meaningfully —
# same manual-versioning convention as scoring_weights.version ("v1").
DATASET_VERSION = "cnamuangtoun-onet-v1"
RELEVANCE_THRESHOLD = 0.5
TRAINED_MODEL_TYPES = ["logistic_regression", "random_forest", "xgboost", "lightgbm", "lightgbm_ranker"]


def _rule_based_scores(df) -> np.ndarray:
    return np.array(
        [
            rule_based_score(FeatureVector(**{name: float(row[name]) for name in FEATURE_NAMES}), DEFAULT_WEIGHTS)
            for _, row in df.iterrows()
        ]
    )


def _normalize_to_unit_range(scores: np.ndarray) -> np.ndarray:
    """Only used for lightgbm_ranker: LambdaRank produces relative margin
    scores, not calibrated [0,1] probabilities, so a 0.5 classification
    threshold means nothing on the raw scale. Min-max normalizing within
    the split being scored makes the threshold meaningful. ROC-AUC/NDCG/
    MRR don't need this — all three are rank-order invariant."""
    lo, hi = scores.min(), scores.max()
    if hi == lo:
        return np.full_like(scores, 0.5)
    return (scores - lo) / (hi - lo)


def _model_scores(model_type: str, df) -> np.ndarray:
    if model_type == "rule_based":
        return _rule_based_scores(df)
    if model_type == "embedding_cosine":
        return df[EMBEDDING_COSINE_BASELINE_COLUMN].to_numpy()
    trained = load_model(model_type)
    X = df[FEATURE_NAMES]
    if model_type == "logistic_regression":
        return trained.estimator.predict_proba(X)[:, 1]
    return np.asarray(trained.estimator.predict(X), dtype=float)


def _compute_metrics(df, scores: np.ndarray, model_type: str) -> dict[str, float | int | None]:
    labels = df["label"].to_numpy()
    y_true_binary = (labels >= RELEVANCE_THRESHOLD).astype(int)

    classification_scores = _normalize_to_unit_range(scores) if model_type == "lightgbm_ranker" else np.clip(scores, 0.0, 1.0)
    y_pred_binary = (classification_scores >= RELEVANCE_THRESHOLD).astype(int)

    return {
        "precision": float(precision_score(y_true_binary, y_pred_binary, zero_division=0)),
        "recall": float(recall_score(y_true_binary, y_pred_binary, zero_division=0)),
        "f1": float(f1_score(y_true_binary, y_pred_binary, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true_binary, scores)) if len(set(y_true_binary)) > 1 else None,
        "ndcg_at_5": ndcg_at_k_grouped(labels.tolist(), scores.tolist(), df["resume_ref"].tolist(), k=5),
        "mrr": mrr_grouped(labels.tolist(), scores.tolist(), df["resume_ref"].tolist()),
        "n": int(len(df)),
    }


async def evaluate_split(split: str) -> dict[str, dict[str, dict[str, float | int | None]]]:
    """Returns {model_type: {label_source: metrics}}."""
    async with SessionLocal() as session:
        taxonomy = await load_taxonomy_from_db(session)
        embedding_service = get_embedding_service()
        df = await load_or_build_feature_matrix(session, taxonomy, embedding_service)

    split_df = df[df.dataset_split == split].reset_index(drop=True)
    label_sources = sorted(split_df["label_source"].unique())
    print(f"'{split}' split: {len(split_df)} rows across label sources: {label_sources}")

    results: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for model_type in ["rule_based", "embedding_cosine"] + TRAINED_MODEL_TYPES:
        try:
            scores = _model_scores(model_type, split_df)
        except FileNotFoundError:
            print(f"  [{model_type}] no saved model in backend/data/models/ — skipping (run train_model.py first)")
            continue

        per_source: dict[str, dict[str, float | int | None]] = {}
        for label_source in label_sources:
            mask = (split_df["label_source"] == label_source).to_numpy()
            per_source[label_source] = _compute_metrics(split_df[mask].reset_index(drop=True), scores[mask], model_type)
        results[model_type] = per_source

    return results


def _print_report(results: dict) -> None:
    for model_type, per_source in results.items():
        print(f"\n=== {model_type} ===")
        for label_source, metrics in per_source.items():
            formatted = ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items())
            print(f"  [{label_source}] {formatted}")


def _hyperparameters_for(model_type: str) -> dict:
    if model_type == "rule_based":
        return DEFAULT_WEIGHTS
    if model_type == "embedding_cosine":
        return {}
    return load_model(model_type).hyperparameters


async def main(split: str) -> None:
    print(f"Evaluating on the '{split}' split...")
    print(
        "Note: no human_annotated gold-set rows exist yet (docs/DATASET_STRATEGY.md §3 calls this "
        "'recommended, not yet collected') -- metrics below are broken out per label_source; DATASET_STRATEGY.md "
        "is explicit that none of the existing sources alone is a validated headline number."
    )
    results = await evaluate_split(split)
    _print_report(results)

    async with SessionLocal() as session:
        for model_type, per_source in results.items():
            features = [EMBEDDING_COSINE_BASELINE_COLUMN] if model_type == "embedding_cosine" else FEATURE_NAMES
            await log_experiment(
                session,
                name=f"{model_type}_{split}",
                model_type=model_type,
                dataset_version=DATASET_VERSION,
                features=features,
                hyperparameters=_hyperparameters_for(model_type),
                metrics=per_source,
            )
        await session.commit()
    print("\nLogged to MLflow and mirrored into the experiments table.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    args = parser.parse_args()
    asyncio.run(main(args.split))
