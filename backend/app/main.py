"""FastAPI application entrypoint.

Phase 8: wires the endpoints from docs/ARCHITECTURE.md §10 to Phases 1-7.
`/matches` returns score + feature breakdown only — no explanation field,
since that's Phase 12's LLM layer and isn't built yet. `/resumes/{id}/recommendations`
isn't implemented for the same reason: it's explanation/recommendation
territory, not scoring.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import jobs, matches, resumes, skills
from app.config import get_settings
from app.db import SessionLocal, engine
from app.services.taxonomy_loader import load_taxonomy_from_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionLocal() as session:
        app.state.taxonomy = await load_taxonomy_from_db(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Resume-Job Matching & Optimization System",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(resumes.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": str(exc.status_code), "message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"error": {"code": "422", "message": "Request validation failed", "detail": exc.errors()}}
    )


@app.get("/health")
async def health() -> dict:
    """Liveness/readiness check: confirms the app is up and the DB is reachable."""
    settings = get_settings()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}
