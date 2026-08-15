"""rent_stats DB 연결."""

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


def resolved_rent_database_url() -> str:
    explicit = (settings.rent_database_url or "").strip()
    if explicit:
        return _normalize_url(explicit)
    base = (settings.database_url or "").strip()
    if "/land_stats" in base:
        return _normalize_url(base.replace("/land_stats", "/rent_stats"))
    return ""


@lru_cache
def get_rent_engine() -> Engine | None:
    url = resolved_rent_database_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


def get_rent_db():
    eng = get_rent_engine()
    if eng is None:
        raise RuntimeError("RENT_DATABASE_URL not configured")
    factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()
