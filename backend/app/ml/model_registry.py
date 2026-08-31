"""Trained-model persistence (Phase 11). No MLflow Model Registry, no
database-backed registry — a flat joblib file per model_type under
backend/data/models/ is the whole mechanism, matching this project's
"proportionate scope" pattern (docs/ROADMAP.md's working agreement):
there's one active model per type, chosen by evaluate.py's own metrics,
not a fleet of versions needing a registry to arbitrate between.

Lives under backend/data/, not the repo-root models/ scaffold directory,
for the same Docker bind-mount reason as app/ml/dataset_loader.py's
PROCESSED_DIR — see that module's docstring.
"""
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"


@dataclass(frozen=True)
class TrainedModel:
    model_type: str
    estimator: Any
    feature_names: list[str]
    hyperparameters: dict
    trained_at: str


def save_model(model_type: str, estimator: Any, feature_names: list[str], hyperparameters: dict) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / f"{model_type}.joblib"
    trained_at = datetime.now(UTC).isoformat()
    joblib.dump(
        {
            "model_type": model_type,
            "estimator": estimator,
            "feature_names": feature_names,
            "hyperparameters": hyperparameters,
            "trained_at": trained_at,
        },
        path,
    )
    # A small sidecar .json next to the .joblib so hyperparameters/trained_at
    # are human-inspectable without unpickling (the estimator itself isn't
    # JSON-safe, so this is metadata-only, not a full second copy).
    (MODELS_DIR / f"{model_type}.json").write_text(
        json.dumps({"model_type": model_type, "feature_names": feature_names, "hyperparameters": hyperparameters, "trained_at": trained_at}, indent=2)
    )
    return path


def load_model(model_type: str) -> TrainedModel:
    path = MODELS_DIR / f"{model_type}.joblib"
    payload = joblib.load(path)
    return TrainedModel(**payload)
