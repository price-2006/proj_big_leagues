"""Phase 14 test procedure per docs/ROADMAP.md: "rate limiter returns 429
past threshold." Exercises the real Limiter instance and real Redis
backend from app/rate_limiter.py — the same object POST /resumes, /jobs,
and /matches are decorated with — against a throwaway endpoint rather
than a real upload, so this test is fast and deterministic instead of
needing 11 real spaCy-parsed resume uploads to exhaust the real
10/minute limit. A fresh, uuid-suffixed path per test run gives an
independent Redis-backed counter, so this doesn't go flaky if run twice
within the same minute (the underlying storage is real and persists).
"""
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.rate_limiter import limiter


@pytest_asyncio.fixture
async def rate_limited_probe():
    limiter.enabled = True
    path = f"/probe-{uuid.uuid4().hex}"

    probe_app = FastAPI()
    probe_app.state.limiter = limiter
    probe_app.add_middleware(SlowAPIMiddleware)

    @probe_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"error": {"code": "429", "message": str(exc.detail)}})

    @probe_app.get(path)
    @limiter.limit("3/minute")
    async def probe(request: Request) -> dict:
        return {"ok": True}

    transport = ASGITransport(app=probe_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, path

    limiter.enabled = False


@pytest.mark.asyncio
async def test_rate_limiter_returns_429_past_threshold(rate_limited_probe):
    client, path = rate_limited_probe

    responses = [await client.get(path) for _ in range(4)]

    assert [r.status_code for r in responses[:3]] == [200, 200, 200]
    assert responses[3].status_code == 429
    assert responses[3].json()["error"]["code"] == "429"
