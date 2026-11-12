"""집합 2단계 Phase A 공통 — 읽기 전용 DB 접속.

로컬 DB(backend/.env)만. 모든 세션 default_transaction_read_only=on + statement_timeout.
접속정보는 출력하지 않는다. 지번이 들어가는 산출물은 logs/collective_p2/(gitignore)에만.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

OUT = ROOT / "logs" / "collective_p2"
OUT.mkdir(parents=True, exist_ok=True)

DBS = {
    "land": lambda: settings.database_url,
    "built": lambda: settings.built_database_url,
    "collective": lambda: settings.collective_database_url,
    "rent": lambda: settings.rent_database_url or settings.database_url.replace("/land_stats", "/rent_stats"),
}


def engine(db: str = "collective", timeout_ms: int = 1_200_000):
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
