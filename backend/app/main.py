"""FastAPI application entrypoint.

Phase 8: wires the endpoints from docs/ARCHITECTURE.md §10 to Phases 1-7.
`/matches` returns score + feature breakdown only — no explanation field;
that's a separate, LLM-backed call. Phase 12 adds
`POST /resumes/{id}/recommendations`, which requires an already-computed
match and never touches its score.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import jobs, matches, resumes, skills
from app.config import get_settings
from app.db import SessionLocal, engine
from app.logging_config import configure_logging
from app.rate_limiter import limiter
from app.services.taxonomy_loader import load_taxonomy_from_db

configure_logging()
logger = logging.getLogger(__name__)


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

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.include_router(resumes.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning("rate limit exceeded: path=%s", request.url.path)
    return JSONResponse(status_code=429, content={"error": {"code": "429", "message": f"Rate limit exceeded: {exc.detail}"}})


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
