#!/bin/sh
# Phase 15: makes "docker compose up" from a clean checkout actually work
# end-to-end with no manual steps beyond .env setup — migrations and skill
# taxonomy seeding used to be steps someone had to run by hand
# (`docker exec ... alembic upgrade head`, `python -m scripts.seed_skills`,
# `python -m scripts.embed_skills`) after every fresh `up`. All three are
# idempotent, so running them on every container start is safe and cheap
# after the first run, not just correct on a truly fresh database.
set -e

alembic upgrade head
python -m scripts.seed_skills
python -m scripts.embed_skills

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
