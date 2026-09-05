FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# build-essential + libpq-dev: needed by asyncpg/psycopg and, from Phase 1
# onward, by PyMuPDF's native deps. curl: used by the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
# --timeout/--retries: this layer downloads torch (~a few hundred MB via
# sentence-transformers' dependency chain), which has been observed
# hitting pip's default read timeout on this network; more patience, not
# a different mirror, is the fix.
RUN pip install --timeout=180 --retries=8 -r requirements.txt \
    && python -m spacy download en_core_web_sm \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY backend/scripts ./scripts

COPY docker/backend-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Longer start-period than Phase 0's: the entrypoint now runs migrations
# plus skill-taxonomy seeding (one of which fetches from O*NET over the
# network) before uvicorn ever starts listening.
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
