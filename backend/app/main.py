"""FastAPI application entrypoint.

Phase 0: just enough to prove the container boots and can reach the
database. Routers are added in Phase 8 once the pipeline components
(parsers, NLP, scoring) exist to back them — see docs/ROADMAP.md.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Resume-Job Matching & Optimization System",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    """Liveness/readiness check: confirms the app is up and the DB is reachable."""
    settings = get_settings()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}
