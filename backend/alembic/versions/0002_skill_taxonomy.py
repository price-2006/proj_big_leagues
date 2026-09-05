"""create skill taxonomy tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-29

Creates skills / skill_aliases / skill_disambiguation_rules per
docs/ARCHITECTURE.md §5, seeded by scripts/seed_skills.py (Phase 5).
`skills.embedding` is nullable: stays unpopulated until the embedding
service lands in Phase 6.
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="internal"),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.UniqueConstraint("canonical_name", name="uq_skills_canonical_name"),
    )

    op.create_table(
        "skill_aliases",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.UniqueConstraint("alias", name="uq_skill_aliases_alias"),
    )
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"])

    op.create_table(
        "skill_disambiguation_rules",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("skill_a_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("skill_b_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("skill_a_id", "skill_b_id", name="uq_disambiguation_pair"),
    )


def downgrade() -> None:
    op.drop_table("skill_disambiguation_rules")
    op.drop_index("ix_skill_aliases_skill_id", table_name="skill_aliases")
    op.drop_table("skill_aliases")
    op.drop_table("skills")
