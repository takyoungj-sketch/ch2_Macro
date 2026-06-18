#!/usr/bin/env python3
"""
Promote 이전 집합·Profile 파이프라인 오케스트레이터 (Phase A~D).

실행:
    cd pipeline
    python finish_collective_pre_promote.py
    python finish_collective_pre_promote.py --smoke-addr1 "세종특별자치시"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LOG_DIR = REPO / "logs"
SNAP_DIR = ROOT / "clean_snapshots" / "collective_pre_promote"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"collective_pre_promote_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("pre_promote")

DEFAULT_DB = os.environ.get(
    "COLLECTIVE_DATABASE_URL",
    "postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats",
)


def _run(cmd: list[str], *, env: dict | None = None) -> int:
    merged = {**os.environ, **(env or {})}
    merged.setdefault("COLLECTIVE_DATABASE_URL", DEFAULT_DB)
    log.info("run: %s", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, env=merged).returncode


def _counts(db_url: str) -> dict:
    eng = create_engine(db_url)
    tables = (
        "collective_building_stats",
        "collective_building_annual_stats",
        "market_stats",
        "market_annual_stats",
        "regional_profile",
    )
    out: dict = {}
    with eng.connect() as conn:
        out["transactions"] = int(conn.execute(text("SELECT COUNT(*) FROM collective_transactions")).scalar() or 0)
        for t in tables:
            exists = conn.execute(text(f"SELECT to_regclass('public.{t}') IS NOT NULL")).scalar()
            out[t] = int(conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() or 0) if exists else None
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", default=DEFAULT_DB)
    p.add_argument("--smoke-addr1", help="시도 한정 스모크 (전국 생략)")
    p.add_argument("--skip-building", action="store_true")
    p.add_argument("--skip-market", action="store_true")
    p.add_argument("--skip-profile", action="store_true")
    p.add_argument("--skip-long-term", action="store_true")
    args = p.parse_args()

    dbname = args.db_url.rsplit("/", 1)[-1]
    if _run([sys.executable, "bootstrap_collective_stats_next.py", "--ddl-only", "--dbname", dbname]) != 0:
        sys.exit(1)

    addr_args = ["--addr1", args.smoke_addr1] if args.smoke_addr1 else []
    steps: list[tuple[str, list[str]]] = []
    if not args.skip_building:
        steps.append(("building_stats", [sys.executable, "build_collective_building_stats.py", *addr_args]))
    if not args.skip_market:
        steps.append(("market_stats", [sys.executable, "build_collective_market_stats.py", *addr_args]))
    if not args.skip_long_term:
        steps.append(("long_term", [sys.executable, "ingest_collective_long_term_annual.py"]))
    if not args.skip_profile and not args.smoke_addr1:
        steps.append(("regional_profile", [sys.executable, "build_regional_profile.py"]))

    for name, cmd in steps:
        rc = _run(cmd, env={"COLLECTIVE_DATABASE_URL": args.db_url})
        if rc != 0 and name != "long_term":
            log.error("step %s failed rc=%s", name, rc)
            sys.exit(rc)
        if rc != 0:
            log.warning("long_term ingest skipped or partial rc=%s", rc)

    summary = _counts(args.db_url)
    summary["finished_at"] = datetime.now().isoformat()
    summary["smoke_addr1"] = args.smoke_addr1
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAP_DIR / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary: %s", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
