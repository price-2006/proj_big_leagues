"""Phase 0 smoke test: Settings load with sane defaults, no DB required.

DB-dependent tests (health endpoint, migrations) are exercised via the
manual test procedure in the Phase 0 section of docs/ROADMAP.md, and get
real automated integration coverage once httpx/test-DB wiring lands in
Phase 8.
"""
from app.config import Settings


def test_settings_defaults(monkeypatch) -> None:
    # _env_file=None only skips the .env *file* — pydantic-settings still
    # reads real process env vars, which this container's docker-compose
    # env_file sets (e.g. LLM_PROVIDER=local, for Phase 12's local dev
    # setup) — so the class-level defaults this test actually checks need
    # those cleared, not just the file disabled.
    for var in ("ENVIRONMENT", "EMBEDDING_MODEL_NAME", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.embedding_model_name == "all-MiniLM-L6-v2"
    assert settings.llm_provider == "anthropic"
