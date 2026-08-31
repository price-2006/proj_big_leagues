"""Logs one evaluate.py run to MLflow, then mirrors the same run into the
`experiments` table (Phase 11, docs/ARCHITECTURE.md §5/§13) — MLflow is
the source of truth for run artifacts, the DB mirror is what makes
results queryable with plain SQL (joined against training_labels, etc.)
without opening the MLflow UI.
"""
import os
import subprocess

import mlflow
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.experiment import Experiment


def _git_commit() -> str | None:
    """Best-effort only: the backend container doesn't bind-mount .git
    (docker-compose.yml only mounts ./backend), so `git rev-parse` has
    nothing to read unless GIT_COMMIT is set explicitly at container
    start. git_commit is nullable in the schema for exactly this case —
    None here is honest, not a bug to work around."""
    if commit := os.environ.get("GIT_COMMIT"):
        return commit
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _log_flat_metrics(metrics: dict[str, dict[str, float | None]]) -> None:
    """metrics is nested {label_source: {precision, recall, ...}} — MLflow
    wants flat key/value pairs, so this flattens as `label_source__metric`.
    None values (a metric that couldn't be computed — e.g. no ranking
    group had 2+ items for that label_source) are skipped, not logged as
    0; mlflow.log_metric rejects None outright, and 0 would misrepresent
    "not computed" as a real, bad score."""
    for label_source, source_metrics in metrics.items():
        for metric_name, value in source_metrics.items():
            if value is not None:
                mlflow.log_metric(f"{label_source}__{metric_name}", value)


async def log_experiment(
    session: AsyncSession,
    name: str,
    model_type: str,
    dataset_version: str,
    features: list[str],
    hyperparameters: dict,
    metrics: dict[str, dict[str, float | None]],
) -> Experiment:
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({"model_type": model_type, "dataset_version": dataset_version, **hyperparameters})
        _log_flat_metrics(metrics)
        mlflow_run_id = run.info.run_id

    experiment = Experiment(
        name=name,
        model_type=model_type,
        dataset_version=dataset_version,
        features=features,
        hyperparameters=hyperparameters,
        metrics=metrics,
        git_commit=_git_commit(),
        mlflow_run_id=mlflow_run_id,
    )
    session.add(experiment)
    await session.flush()
    return experiment
