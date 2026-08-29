"""enable pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-08-29

Enabling the extension via a migration (in addition to docker/postgres/init.sql)
means the schema is reproducible against any fresh Postgres — a managed
instance in deployment, not just the local docker-compose container.
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
