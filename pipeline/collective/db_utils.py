"""collective_stats 전용 DB."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_PIPELINE_DIR = Path(__file__).resolve().parent.parent
_COLLECTIVE_ENV = _PIPELINE_DIR / ".env.collective"
_DEFAULT_ENV = _PIPELINE_DIR / ".env"

if _COLLECTIVE_ENV.is_file():
    load_dotenv(_COLLECTIVE_ENV)
else:
    load_dotenv(_DEFAULT_ENV)


def get_collective_engine() -> Engine:
    url = os.environ.get("COLLECTIVE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url and "collective_stats" not in url and os.environ.get("COLLECTIVE_DATABASE_URL") is None:
        url = url.rsplit("/", 1)[0] + "/collective_stats"
    if not url:
        url = "postgresql+psycopg2://postgres:password@localhost:5432/collective_stats"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


def get_land_engine_for_region_copy() -> Engine:
    import importlib.util

    land_utils = _PIPELINE_DIR / "db_utils.py"
    spec = importlib.util.spec_from_file_location("pipeline_land_db_utils", land_utils)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {land_utils}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_engine()
