"""Phase 0 smoke test: Settings load with sane defaults, no DB required.

DB-dependent tests (health endpoint, migrations) are exercised via the
manual test procedure in the Phase 0 section of docs/ROADMAP.md, and get
real automated integration coverage once httpx/test-DB wiring lands in
Phase 8.
"""
from app.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.embedding_model_name == "all-MiniLM-L6-v2"
    assert settings.llm_provider == "anthropic"
