"""macro_ts_stats 연결. 제품 원장 DB와 분리."""

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


def _sibling_url() -> str:
    explicit = (settings.macro_ts_database_url or "").strip()
    if explicit:
        return _normalize_url(explicit)
    base = (settings.database_url or "").strip()
    if "/land_stats" in base:
        return _normalize_url(base.replace("/land_stats", "/macro_ts_stats"))
    return ""


@lru_cache
def get_macro_ts_engine() -> Engine | None:
    url = _sibling_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


def get_macro_ts_session_factory() -> sessionmaker | None:
    eng = get_macro_ts_engine()
    if eng is None:
        return None
    return sessionmaker(autocommit=False, autoflush=False, bind=eng)


def get_macro_ts_db():
    factory = get_macro_ts_session_factory()
    if factory is None:
        raise RuntimeError("MACRO_TS_DATABASE_URL 없음")
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()
