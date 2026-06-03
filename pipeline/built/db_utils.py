"""built_stats 전용 DB — land pipeline db_utils 와 분리."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_PIPELINE_DIR = Path(__file__).resolve().parent.parent
_BUILT_ENV = _PIPELINE_DIR / ".env.built"
_DEFAULT_ENV = _PIPELINE_DIR / ".env"

if _BUILT_ENV.is_file():
    load_dotenv(_BUILT_ENV)
else:
    load_dotenv(_DEFAULT_ENV)


def get_built_engine() -> Engine:
    url = os.environ.get("BUILT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url and "built_stats" not in url and os.environ.get("BUILT_DATABASE_URL") is None:
        url = url.rsplit("/", 1)[0] + "/built_stats"
    if not url:
        url = "postgresql+psycopg2://postgres:password@localhost:5432/built_stats"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


def get_land_engine_for_region_copy() -> Engine:
    """region_codes 복사용 — land_stats."""
    import importlib.util

    land_utils = _PIPELINE_DIR / "db_utils.py"
    spec = importlib.util.spec_from_file_location("pipeline_land_db_utils", land_utils)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {land_utils}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_engine()
