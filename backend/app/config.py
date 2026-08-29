"""Centralized configuration.

All environment-derived settings go through this single object rather than
scattered os.environ calls, per docs/ARCHITECTURE.md §12. New settings for
later phases (embedding provider, LLM provider) are declared here up front
so .env.example documents the full surface area even before those phases
are implemented.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = (
        "postgresql+asyncpg://resume_matcher:resume_matcher@localhost:5432/resume_matcher"
    )

    # Phase 6
    embedding_model_provider: str = "sentence_transformers"
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # Phase 12
    llm_provider: str = "anthropic"
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
