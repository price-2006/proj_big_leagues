"""SQLAlchemy model for experiments (Phase 11, docs/ARCHITECTURE.md §5).

Mirrors MLflow's own run record (params/metrics/artifacts), not a
replacement for it: `evaluate.py` logs to MLflow first, then mirrors the
same run here via `mlflow_run_id` so results are queryable with plain SQL
(joined against `matches`/`training_labels`, etc.) without opening the
MLflow UI — the exact reasoning ARCHITECTURE.md §13 states.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    model_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'rule_based' | 'embedding_cosine' | 'logistic_regression' | 'random_forest' | 'xgboost' | 'lightgbm' | 'lightgbm_ranker'
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[list] = mapped_column(JSONB, nullable=False)
    hyperparameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {label_source: {precision, recall, f1, roc_auc, ndcg_at_5, mrr}, ...}
    git_commit: Mapped[str | None] = mapped_column(Text, nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
