#!/usr/bin/env python3
"""로컬 또는 VPS에서 ch2_platform DB 생성 + 048 마이그레이션."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_FILES = [
    REPO_ROOT / "db" / "048_ch2_platform.sql",
    REPO_ROOT / "db" / "048b_board_support.sql",
]
ENV_FILE = REPO_ROOT / "backend" / ".env"


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def normalize_psycopg_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgresql+psycopg2://"):
        u = u.replace("postgresql+psycopg2://", "postgresql://", 1)
    return u


def main() -> int:
    env = load_env()
    platform_url = env.get("DATABASE_URL_PLATFORM", "")
    if not platform_url:
        print("ERROR: DATABASE_URL_PLATFORM not set in backend/.env", file=sys.stderr)
        return 1
    missing = [p for p in SQL_FILES if not p.exists()]
    if missing:
        print(f"ERROR: missing {missing[0]}", file=sys.stderr)
        return 1

    psql_url = normalize_psycopg_url(platform_url)
    db_name = psql_url.rsplit("/", 1)[-1].split("?")[0]
    admin_url = psql_url.rsplit("/", 1)[0] + "/postgres"

    print(f"==> ensure database {db_name}")
    conn = psycopg2.connect(admin_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{db_name}" OWNER postgres')
        print(f"created {db_name}")
    else:
        print(f"{db_name} already exists")
    cur.close()
    conn.close()

    conn = psycopg2.connect(psql_url)
    conn.autocommit = True
    cur = conn.cursor()
    for sql_file in SQL_FILES:
        print(f"==> apply {sql_file.name}")
        sql = sql_file.read_text(encoding="utf-8")
        cur.execute(sql)
    cur.close()
    conn.close()

    print("OK: ch2_platform schema applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
