"""Phase C-2 — 로컬 DB 덤프 → 리허설 DB(*_p2r) 복원. 원본 DB는 읽기(pg_dump)만.

덤프: logs/collective_p2/dumps/<db>.dir (pg_dump -Fd -j4) — 롤백 비교 기준(수정 전)으로도 쓴다.
복원: <db>_p2r 를 새로 만들고 pg_restore -j4. 이미 있으면 --recreate 없이는 멈춘다.
접속정보는 출력하지 않는다(PGPASSWORD 는 하위 프로세스 env 로만).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline"))
from collective.migrate_p2_keys import REHEARSAL_RE, server_url_from_env  # noqa: E402

PG = Path(r"C:\Program Files\PostgreSQL\18\bin")
DUMPS = ROOT / "logs" / "collective_p2" / "dumps"
SOURCES = ["collective_stats", "built_stats", "rent_stats"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--skip-dump", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    u = make_url(server_url_from_env())
    env = {**os.environ, "PGPASSWORD": u.password or "", "PGHOST": u.host or "localhost",
           "PGPORT": str(u.port or 5432), "PGUSER": u.username or "postgres"}
    admin = create_engine(u.set(database="postgres", drivername="postgresql+psycopg2"), isolation_level="AUTOCOMMIT")
    DUMPS.mkdir(parents=True, exist_ok=True)
    for src in [s for s in SOURCES if not a.only or s in a.only.split(",")]:
        dst = f"{src}_p2r"
        assert REHEARSAL_RE.match(dst) and dst != src
        d = DUMPS / f"{src}.dir"
        if not a.skip_dump:
            if d.exists():
                raise SystemExit(f"덤프 폴더가 이미 있음: {d} (--skip-dump 로 재사용)")
            t0 = time.time()
            subprocess.run([str(PG / "pg_dump.exe"), "-Fd", "-j", "4", "-f", str(d), src], env=env, check=True)
            print(f"[dump] {src} {time.time()-t0:.0f}s", flush=True)
        with admin.connect() as c:
            exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname=:d"), {"d": dst}).first()
            if exists and not a.recreate:
                raise SystemExit(f"{dst} 이미 있음 (--recreate)")
            if exists:
                c.execute(text(f"DROP DATABASE {dst} WITH (FORCE)"))
            c.execute(text(f"CREATE DATABASE {dst}"))
        t0 = time.time()
        subprocess.run([str(PG / "pg_restore.exe"), "-j", "4", "--no-owner", "-d", dst, str(d)], env=env, check=True)
        print(f"[restore] {dst} {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
