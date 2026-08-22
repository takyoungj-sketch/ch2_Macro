from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_PIPELINE = Path(__file__).resolve().parents[1]
_BACKEND_ENV = _PIPELINE.parent / "backend" / ".env"

if _BACKEND_ENV.is_file():
    load_dotenv(_BACKEND_ENV)
load_dotenv(_PIPELINE / ".env.collective")
load_dotenv(_PIPELINE / ".env")


def _as_psycopg(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_parcel_engine() -> Engine:
    url = os.environ.get("PARCEL_MASTER_DATABASE_URL")
    if not url:
        base = (
            os.environ.get("COLLECTIVE_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or "postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats"
        )
        url = _as_psycopg(base).rsplit("/", 1)[0] + "/parcel_master"
    return create_engine(_as_psycopg(url), pool_pre_ping=True)


def get_collective_engine() -> Engine:
    url = os.environ.get("COLLECTIVE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        url = "postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats"
    return create_engine(_as_psycopg(url), pool_pre_ping=True)


def admin_url() -> str:
    return os.environ.get(
        "COLLECTIVE_ADMIN_URL",
        "postgresql://postgres:8972@localhost:5432/postgres",
    )
