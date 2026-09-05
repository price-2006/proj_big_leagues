"""create resumes, jobs, matches tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30

Phase 8, docs/ARCHITECTURE.md §5. `match_explanations` is deliberately
not created here — Phase 12's LLM layer is what would ever write to it;
same reasoning `training_labels`/`experiments` stay deferred to Phases
10/11. `resumes.owner_id`/`jobs.owner_id` have no FK: no `users` table
exists anywhere in the roadmap, auth stays deferred throughout.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_profile", postgresql.JSONB(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("file_type IN ('pdf', 'docx')", name="ck_resumes_file_type"),
    )

    op.create_table(
        "jobs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_profile", postgresql.JSONB(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "matches",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("feature_vector", postgresql.JSONB(), nullable=False),
        sa.Column("rule_based_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("ml_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("scoring_model_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("resume_id", "job_id", "scoring_model_version", name="uq_match_version"),
    )
    op.create_index("ix_matches_resume_id", "matches", ["resume_id"])


def downgrade() -> None:
    op.drop_index("ix_matches_resume_id", table_name="matches")
    op.drop_table("matches")
    op.drop_table("jobs")
    op.drop_table("resumes")
