"""집합 1단계 공통 (0단계 _db.py 사본, 출력만 logs/collective_p1) — 읽기 전용 DB 접속.

로컬 DB(backend/.env DATABASE_URL)만 사용한다. 모든 세션은
SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY + statement_timeout.
접속정보는 출력하지 않는다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

OUT = ROOT / "logs" / "collective_p1"  # gitignore 대상(로컬 표본)
OUT.mkdir(parents=True, exist_ok=True)


DBS = {
    "land": lambda: settings.database_url,
    "built": lambda: settings.built_database_url,
    "collective": lambda: settings.collective_database_url,
    "rent": lambda: settings.rent_database_url or settings.database_url.replace("/land_stats", "/rent_stats"),
    "macro_ts": lambda: settings.macro_ts_database_url,
}


def engine(db: str = "collective", timeout_ms: int = 600_000):
    """읽기 전용 엔진: 접속 옵션으로 default_transaction_read_only=on + statement_timeout."""
    url = DBS[db]() or settings.database_url
    opts = f"-c default_transaction_read_only=on -c statement_timeout={int(timeout_ms)}"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


def q(conn, sql: str, **params):
    return conn.execute(text(sql), params).fetchall()


def md_table(rows, headers) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r) + " |")
    return "\n".join(out)
