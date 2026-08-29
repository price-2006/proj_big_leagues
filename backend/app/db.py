"""Async SQLAlchemy engine/session — the single place DB access is wired up.

`Base` is imported by alembic/env.py for autogenerate support; it's empty
until Phase 8 adds real models under app/models/.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session scoped to one request."""
    async with SessionLocal() as session:
        yield session
