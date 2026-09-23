"""Database wiring shared by ingestion and future retrieval services.

The URL is configured through ``DATABASE_URL``. SQLite is the zero-config
developer default; PostgreSQL needs no model changes in production.
"""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    # Supabase and Render commonly present a generic ``postgresql://`` URI.
    # Pin it to the installed psycopg v3 driver rather than silently asking
    # SQLAlchemy for the unrelated psycopg2 package.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite"):
        database_path = make_url(url).database
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI-compatible session dependency for future route integration."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def initialize_database(database_url: str | None = None) -> None:
    """Create schema for local/bootstrap deployments.

    Production deployments should execute versioned Alembic migrations before
    application startup; this helper is intentionally safe and idempotent.
    """
    Base.metadata.create_all(get_engine(database_url))
