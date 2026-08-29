"""create text_embeddings table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29

Stores per-chunk embeddings for resume experience/project bullets and JD
responsibility lines (Phase 6, docs/ARCHITECTURE.md §5). `entity_id` has
no FK — polymorphic (resumes/jobs tables land in Phase 8).
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_ENTITY_TYPES = ("resume_experience", "resume_project", "job_responsibility")


def upgrade() -> None:
    op.create_table(
        "text_embeddings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.CheckConstraint(f"entity_type IN {_ENTITY_TYPES}", name="ck_text_embeddings_entity_type"),
    )
    op.create_index("ix_text_embeddings_entity", "text_embeddings", ["entity_type", "entity_id"])
    op.execute(
        "CREATE INDEX text_embeddings_ivfflat ON text_embeddings USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS text_embeddings_ivfflat")
    op.drop_index("ix_text_embeddings_entity", table_name="text_embeddings")
    op.drop_table("text_embeddings")
