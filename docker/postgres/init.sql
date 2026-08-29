-- Runs once, on first container init, via docker-entrypoint-initdb.d.
-- The pgvector/pgvector image ships the extension binary; this just enables it.
-- Also done idempotently in the first Alembic migration (0001) so a fresh
-- managed Postgres instance without this init script still ends up correct.
CREATE EXTENSION IF NOT EXISTS vector;
