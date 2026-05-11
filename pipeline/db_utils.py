"""DB 연결 유틸리티 (pipeline 공용)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        user = os.environ.get("DB_USER", "postgres")
        password = os.environ.get("DB_PASSWORD", "")
        dbname = os.environ.get("DB_NAME", "land_stats")
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url, pool_pre_ping=True)


def execute_sql_file(engine: Engine, path: str) -> None:
    """SQL 파일 전체를 실행한다."""
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    with engine.begin() as conn:
        conn.execute(text(sql))
