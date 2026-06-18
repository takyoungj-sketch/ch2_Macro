#!/usr/bin/env python3
"""
집합 Phase A 마무리 — DDL 적용, building_stats mart 적재, 스모크 검증.

실행:
    cd pipeline
    set COLLECTIVE_DATABASE_URL=postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats
    python finish_collective_phase_a.py

    # parallel DB (land_stats_next 패턴)
    python finish_collective_phase_a.py --dbname collective_stats_next --bootstrap
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
SNAP_DIR = ROOT / "clean_snapshots" / "collective_phase_a"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"collective_phase_a_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("finish_collective_phase_a")

DEFAULT_DB = os.environ.get(
    "COLLECTIVE_DATABASE_URL",
    "postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats",
)


def _run(cmd: list[str], *, env: dict | None = None) -> int:
    merged = {**os.environ, **(env or {})}
    log.info("run: %s", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, env=merged).returncode


def _counts(db_url: str) -> dict:
    eng = create_engine(db_url)
    with eng.connect() as conn:
        tx = conn.execute(text("SELECT COUNT(*) FROM collective_transactions")).scalar()
        cbs = conn.execute(
            text("SELECT to_regclass('public.collective_building_stats') IS NOT NULL")
        ).scalar()
        cbas = conn.execute(
            text("SELECT to_regclass('public.collective_building_annual_stats') IS NOT NULL")
        ).scalar()
        mart_n = (
            conn.execute(text("SELECT COUNT(*) FROM collective_building_stats")).scalar()
            if cbs
            else 0
        )
        annual_n = (
            conn.execute(text("SELECT COUNT(*) FROM collective_building_annual_stats")).scalar()
            if cbas
            else 0
        )
        snap = conn.execute(
            text(
                """
                SELECT as_of_month, window_years, COUNT(*)::int AS n
                FROM collective_building_stats
                GROUP BY 1, 2
                ORDER BY 1 DESC, 2 DESC
                LIMIT 5
                """
            )
        ).mappings().all() if cbs and mart_n else []
    return {
        "transactions": int(tx or 0),
        "building_stats_rows": int(mart_n or 0),
        "annual_stats_rows": int(annual_n or 0),
        "snapshots": [
            {
                "as_of_month": r["as_of_month"].isoformat() if r["as_of_month"] else None,
                "window_years": int(r["window_years"]),
                "n": int(r["n"]),
            }
            for r in snap
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", default=DEFAULT_DB)
    p.add_argument("--dbname", help="ddl-only/bootstrap용 DB 이름 (admin URL 기준)")
    p.add_argument("--bootstrap", action="store_true", help="collective_stats_next 전체 bootstrap")
    p.add_argument("--ddl-only", action="store_true", help="023 mart DDL만 적용")
    p.add_argument("--skip-build", action="store_true")
    p.add_argument("--addr1", help="build 스모크: 단일 시도만")
    args = p.parse_args()

    db_url = args.db_url
    if args.bootstrap:
        rc = _run(
            [sys.executable, "bootstrap_collective_stats_next.py"],
            env={"DATABASE_URL": db_url},
        )
        if rc != 0:
            sys.exit(rc)
        base = db_url.rsplit("/", 1)[0]
        db_url = f"{base}/collective_stats_next"
    el    if args.ddl_only:
        dbname = args.dbname or db_url.rsplit("/", 1)[-1]
        rc = _run(
            [
                sys.executable,
                "bootstrap_collective_stats_next.py",
                "--ddl-only",
                "--dbname",
                dbname,
            ]
        )
        if rc != 0:
            sys.exit(rc)
        db_url = f"{db_url.rsplit('/', 1)[0]}/{dbname}"

    if not args.skip_build:
        build_cmd = [sys.executable, "build_collective_building_stats.py"]
        if args.addr1:
            build_cmd.extend(["--addr1", args.addr1])
        rc = _run(build_cmd, env={"COLLECTIVE_DATABASE_URL": db_url})
        if rc != 0:
            sys.exit(rc)

    _run_meta(db_url)
    summary = _counts(db_url)
    summary["database_url"] = db_url.split("@")[-1]
    summary["finished_at"] = datetime.now().isoformat()
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAP_DIR / "finish_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary written: %s", out)
    log.info(
        "tx=%s mart=%s annual=%s snapshots=%s",
        f"{summary['transactions']:,}",
        f"{summary['building_stats_rows']:,}",
        f"{summary['annual_stats_rows']:,}",
        summary["snapshots"],
    )
    if summary["transactions"] > 0 and summary["building_stats_rows"] == 0 and not args.skip_build:
        log.error("mart empty but transactions exist — build_collective_building_stats 점검")
        sys.exit(1)


def _run_meta(db_url: str) -> None:
    """region_sigungu_meta — collective DB에 region_codes 가 있을 때만."""
    eng = create_engine(db_url)
    try:
        with eng.connect() as conn:
            has = conn.execute(text("SELECT to_regclass('public.region_codes') IS NOT NULL")).scalar()
        if not has:
            log.info("region_codes 없음 — build_region_sigungu_meta 스킵")
            return
    except Exception as exc:
        log.info("region meta check skipped: %s", exc)
        return
    rc = _run(
        [sys.executable, "build_region_sigungu_meta.py"],
        env={"DATABASE_URL": db_url},
    )
    if rc != 0:
        log.warning("build_region_sigungu_meta 실패(rc=%s) — Phase A mart에는 필수 아님", rc)


if __name__ == "__main__":
    main()
