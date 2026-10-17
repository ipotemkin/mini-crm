"""Database engine, session and SQLite pragmas."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.models.base import Base

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    path = url.removeprefix("sqlite:///")
    if path in {":memory:", ""} or path.startswith("file:"):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _register_sqlite_hooks(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

        def nocase_ru(s1: str | None, s2: str | None) -> int:
            a = (s1 or "").casefold().replace("ё", "е")
            b = (s2 or "").casefold().replace("ё", "е")
            if a < b:
                return -1
            if a > b:
                return 1
            return 0

        dbapi_connection.create_collation("NOCASE_RU", nocase_ru)


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        settings = get_settings()
        _ensure_sqlite_parent(settings.database_url)
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            future=True,
        )
        if settings.database_url.startswith("sqlite"):
            _register_sqlite_hooks(_engine)
        SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _engine


def get_db() -> Generator[Session, None, None]:
    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db_for_tests(url: str = "sqlite://") -> Engine:
    """Reset engine for tests (shared in-memory via StaticPool)."""
    global _engine, SessionLocal
    # Ensure all models are registered on Base.metadata
    import app.models  # noqa: F401

    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    _register_sqlite_hooks(_engine)
    SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    Base.metadata.create_all(_engine)
    return _engine
