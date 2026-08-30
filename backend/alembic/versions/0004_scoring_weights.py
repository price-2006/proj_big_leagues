"""create scoring_weights table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30

Config table for the rule-based scorer's weights (Phase 7,
docs/ARCHITECTURE.md §8) — a data change instead of a rewrite once
Phase 11 replaces/augments them with a learned model. Not in Architecture
§5's SQL block (that section predates this table being named in prose),
so schema + the seeded row are this phase's own design.

The seeded weights are a literal, point-in-time copy of
app/ml/rule_based_scorer.py's DEFAULT_WEIGHTS, not an import of it —
migrations should stay replayable even if that module changes later; keep
the two in sync by hand if DEFAULT_WEIGHTS ever changes.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scoring_weights",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("version", sa.Text(), nullable=False, unique=True),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute(
        """
        INSERT INTO scoring_weights (version, weights, is_active) VALUES (
            'v1',
            '{
                "required_skill_coverage": 0.35,
                "semantic_experience_similarity": 0.20,
                "project_relevance_similarity": 0.15,
                "preferred_skill_coverage": 0.10,
                "education_match": 0.10,
                "seniority_and_experience_composite": 0.10
            }'::jsonb,
            true
        )
        """
    )


def downgrade() -> None:
    op.drop_table("scoring_weights")
