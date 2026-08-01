"""ch2_platform DB 연결."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _normalize_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgresql://"):
        u = u.replace("postgresql://", "postgresql+psycopg2://", 1)
    return u


@lru_cache
def get_platform_engine() -> Engine | None:
    url = (settings.platform_database_url or "").strip()
    if not url:
        return None
    return create_engine(_normalize_url(url), pool_pre_ping=True)


def get_platform_session_factory() -> sessionmaker | None:
    eng = get_platform_engine()
    if eng is None:
        return None
    return sessionmaker(autocommit=False, autoflush=False, bind=eng)


def get_platform_db():
    """FastAPI Depends — ch2_platform 세션."""
    factory = get_platform_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL_PLATFORM not configured")
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()
