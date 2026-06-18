"""
장기추세(Phase 2b) 오케스트레이터:
  1) 구 DB annual 2010~2020 복사
  2) 신 원장 기준 2021~2026 annual + upper 재빌드
  3) 요약 JSON 저장

예)
  python finish_annual_long_term.py
  python finish_annual_long_term.py --skip-copy
  python finish_annual_long_term.py --years-rebuild 2021-2026
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
    out: dict = {}
    with engine.connect() as conn:
        for table in ("land_annual_stats", "land_annual_upper_stats"):
            rows = conn.execute(
                text(
                    f"""
                    SELECT calendar_year, COUNT(*)::bigint AS n
                    FROM {table}
                    GROUP BY 1 ORDER BY 1
                    """
                )
            ).fetchall()
            out[table] = {
                "total_rows": sum(int(r.n) for r in rows),
                "year_min": int(rows[0].calendar_year) if rows else None,
                "year_max": int(rows[-1].calendar_year) if rows else None,
                "by_year": {int(r.calendar_year): int(r.n) for r in rows},
            }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="장기추세 annual Phase 2b")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--copy-year-to", type=int, default=2020)
    parser.add_argument("--years-rebuild", default="2021-2026")
    parser.add_argument("--skip-copy", action="store_true")
    parser.add_argument("--skip-rebuild", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    snap_dir = ROOT / "pipeline" / "clean_snapshots" / "rebuild_2021_2026"
    snap_dir.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "logs" / "rebuild_annual_long_term.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    status = "ok"
    error: str | None = None

    try:
        if not args.skip_copy:
            cmd = [
                sys.executable,
                str(PIPELINE / "copy_annual_from_legacy.py"),
                "--source-url",
                args.source_url,
                "--year-to",
                str(args.copy_year_to),
            ]
            if args.dry_run:
                cmd.append("--dry-run")
            log.info("Step 1: copy historical annual ≤%d", args.copy_year_to)
            subprocess.run(cmd, check=True, cwd=str(PIPELINE))

        if not args.skip_rebuild and not args.dry_run:
            env = os.environ.copy()
            log.info("Step 2: rebuild annual %s", args.years_rebuild)
            subprocess.run(
                [
                    sys.executable,
                    str(PIPELINE / "build_annual_stats.py"),
                    "--years",
                    args.years_rebuild,
                    "--full",
                    "--with-upper",
                ],
                check=True,
                cwd=str(PIPELINE),
                env=env,
            )
    except subprocess.CalledProcessError as exc:
        status = "error"
        error = f"subprocess exit {exc.returncode}"
        log.exception("finish_annual_long_term failed")
    except Exception as exc:
        status = "error"
        error = str(exc)
        log.exception("finish_annual_long_term failed")

    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error,
        "copy_year_to": args.copy_year_to,
        "years_rebuild": args.years_rebuild,
        "tables": _summary() if not args.dry_run else {},
    }
    out_path = snap_dir / "annual_long_term_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("summary → %s", out_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
