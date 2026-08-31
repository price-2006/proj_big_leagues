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

    # Phase 3
    spacy_model: str = "en_core_web_sm"

    # Phase 8
    upload_dir: str = "./data/uploads"

    # Phase 6
    embedding_model_provider: str = "sentence_transformers"
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # Phase 12
    llm_provider: str = "anthropic"
    llm_api_key: str | None = None

    # Phase 11: SQLite, not a plain "./mlruns" directory — MLflow 3.x puts
    # its filesystem store in maintenance mode and refuses to write to it
    # (found by actually running evaluate.py, not by reading changelogs);
    # docs/ARCHITECTURE.md §4/§14 sanctions "local file/SQLite backend to
    # start" either way, so SQLite is the one that still works. Relative
    # to the backend container's cwd, same convention as upload_dir above.
    # No dedicated MLflow server/UI container is stood up for this.
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment_name: str = "resume_job_matching"


@lru_cache
def get_settings() -> Settings:
    return Settings()
