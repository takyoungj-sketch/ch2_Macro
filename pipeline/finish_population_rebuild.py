"""
인구(Phase 2-5) 오케스트레이터:
  1) 구 DB population_stats 복사
  2) (선택) data/population CSV 추가 적재
  3) 요약 JSON

예)
  python finish_population_rebuild.py
  python finish_population_rebuild.py --skip-copy
  python finish_population_rebuild.py --seed-csv ../data/population/지역별(법정동) 성별 연령별 주민등록 인구수_20260331.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PIPELINE = Path(__file__).resolve().parent
ROOT = PIPELINE.parent
load_dotenv(PIPELINE / ".env.rebuild")
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

DEFAULT_SOURCE = "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats"


def _engine():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats_next",
    )
    return create_engine(url, pool_pre_ping=True)


def _summary() -> dict:
    engine = _engine()
    with engine.connect() as conn:
        total = int(conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar() or 0)
        by_ym = conn.execute(
            text(
                """
                SELECT stats_year, stats_month, COUNT(*)::bigint AS n,
                       SUM(total_population)::bigint AS pop_sum
                FROM population_stats
                GROUP BY 1, 2 ORDER BY 1, 2
                """
            )
        ).fetchall()
        match = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT ps.admin_code)
                FROM population_stats ps
                JOIN region_codes rc
                  ON rc.beopjungri_code = btrim(ps.admin_code::text)
                WHERE ps.admin_level = 'beopjungri'
                """
            )
        ).scalar()
    return {
        "total_rows": total,
        "by_year_month": [
            {
                "stats_year": int(r.stats_year),
                "stats_month": int(r.stats_month) if r.stats_month is not None else None,
                "rows": int(r.n),
                "total_population_sum": int(r.pop_sum or 0),
            }
            for r in by_ym
        ],
        "beopjungri_codes_matching_region_codes": int(match or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="population_stats Phase 2-5")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--skip-copy", action="store_true")
    parser.add_argument(
        "--seed-csv",
        action="append",
        default=[],
        help="복사 후 추가 적재할 CSV (seed_population_csv.py)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    snap_dir = ROOT / "pipeline" / "clean_snapshots" / "rebuild_2021_2026"
    snap_dir.mkdir(parents=True, exist_ok=True)

    status = "ok"
    error: str | None = None

    try:
        if not args.skip_copy:
            cmd = [
                sys.executable,
                str(PIPELINE / "copy_population_from_legacy.py"),
                "--source-url",
                args.source_url,
            ]
            if args.dry_run:
                cmd.append("--dry-run")
            log.info("Step 1: copy population_stats from legacy")
            subprocess.run(cmd, check=True, cwd=str(PIPELINE))

        if args.seed_csv and not args.dry_run:
            env = os.environ.copy()
            for csv_path in args.seed_csv:
                p = Path(csv_path)
                if not p.is_file():
                    p = (ROOT / csv_path).resolve()
                if not p.is_file():
                    raise FileNotFoundError(f"CSV not found: {csv_path}")
                log.info("Step 2: seed %s", p.name)
                subprocess.run(
                    [sys.executable, str(PIPELINE / "seed_population_csv.py"), "--file", str(p)],
                    check=True,
                    cwd=str(PIPELINE),
                    env=env,
                )
    except subprocess.CalledProcessError as exc:
        status = "error"
        error = f"subprocess exit {exc.returncode}"
        log.exception("finish_population_rebuild failed")
    except Exception as exc:
        status = "error"
        error = str(exc)
        log.exception("finish_population_rebuild failed")

    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error,
        "population_stats": _summary() if not args.dry_run else {},
    }
    out_path = snap_dir / "population_rebuild_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary → %s", out_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
