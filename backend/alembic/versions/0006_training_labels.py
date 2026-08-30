"""create training_labels table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-30

Phase 10, docs/ARCHITECTURE.md §5. resume_id/job_id are nullable with
external_resume_ref/external_job_ref alongside them, since most rows come
from an external dataset never inserted into resumes/jobs (see
app/models/training_label.py).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_labels",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("external_resume_ref", sa.Text(), nullable=True),
        sa.Column("external_job_ref", sa.Text(), nullable=True),
        sa.Column("label", sa.Numeric(5, 2), nullable=False),
        sa.Column("label_source", sa.Text(), nullable=False),
        sa.Column("dataset_split", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("dataset_split IN ('train', 'val', 'test')", name="ck_training_labels_split"),
    )
    op.create_index("ix_training_labels_split", "training_labels", ["dataset_split"])
    op.create_index("ix_training_labels_source", "training_labels", ["label_source"])


def downgrade() -> None:
    op.drop_index("ix_training_labels_source", table_name="training_labels")
    op.drop_index("ix_training_labels_split", table_name="training_labels")
    op.drop_table("training_labels")
