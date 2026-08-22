"""로컬 parcel_master 연결. 없으면 None · probe 실패."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

UNAVAILABLE = "로컬 대장DB(parcel_master)가 없습니다. 이 화면은 이 PC에서만 됩니다."


def _normalize_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgresql://"):
        u = u.replace("postgresql://", "postgresql+psycopg2://", 1)
    return u


def parcel_master_url() -> str | None:
    explicit = (settings.parcel_master_database_url or "").strip()
    if explicit:
        return _normalize_url(explicit)
    coll = (settings.collective_database_url or "").strip()
    if not coll:
        return None
    base = _normalize_url(coll).rsplit("/", 1)[0]
    return f"{base}/parcel_master"


@lru_cache
def get_parcel_engine() -> Engine | None:
    url = parcel_master_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0)


def parcel_db_available() -> bool:
    eng = get_parcel_engine()
    if eng is None:
        return False
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM parcel LIMIT 1"))
        return True
    except Exception:
        return False
