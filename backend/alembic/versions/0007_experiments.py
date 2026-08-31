"""create experiments table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-30

Phase 11, docs/ARCHITECTURE.md §5. Mirrors MLflow run records so results
are queryable without opening the MLflow UI (see app/models/experiment.py).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("model_type", sa.Text(), nullable=False),
        sa.Column("dataset_version", sa.Text(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("hyperparameters", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("git_commit", sa.Text(), nullable=True),
        sa.Column("mlflow_run_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_experiments_model_type", "experiments", ["model_type"])


def downgrade() -> None:
    op.drop_index("ix_experiments_model_type", table_name="experiments")
    op.drop_table("experiments")
