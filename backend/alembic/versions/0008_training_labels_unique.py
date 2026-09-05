"""add unique constraint to training_labels

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-30

Real bug found by actually re-running build_dataset.py: `_upsert_label`'s
`ON CONFLICT DO NOTHING` had no constraint to conflict on — `id` is a
fresh uuid4() every insert, and nothing else was unique — so every
re-run silently doubled the table (10,081 -> 20,162 rows, confirmed live
via `SELECT count(*)`). Scoped to (external_resume_ref, external_job_ref,
label_source) because that's 100% of what exists today (see
app/models/training_label.py); a resume_id/job_id-keyed uniqueness rule
for real-upload training rows can be added when that path exists, not
speculatively now.

De-duplicates existing rows first (keeps one arbitrary-but-deterministic
row per group, by `id`) since the corrupted 20,162-row state can't have
a unique index built on top of it otherwise. Ordering by `created_at`
alone doesn't break ties: every row from one build_dataset.py run shares
the exact same `created_at` (Postgres's `now()` is transaction-start
time, and the whole run commits in one transaction) — found this the
hard way when the first version of this migration's DELETE left exact
duplicates behind and the CREATE UNIQUE INDEX below still failed.
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM training_labels
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY external_resume_ref, external_job_ref, label_source
                    ORDER BY id
                ) AS rn
                FROM training_labels
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_training_labels_external_pair_source",
        "training_labels",
        ["external_resume_ref", "external_job_ref", "label_source"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_training_labels_external_pair_source", "training_labels", type_="unique")
