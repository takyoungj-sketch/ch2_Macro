"""
로컬 개발 DB 전용: 매핑 재정제 + V2·상위 사전집계 재구축 + before/after 로그.

  cd pipeline
  py -3.13 run_local_rebuild.py --as-of 2025-12-01 --windows 3,5

전제: DATABASE_URL 이 로컬 DB. 운영 DB 금지.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from db_utils import execute_sql_file, get_engine

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LOGS = REPO / "logs"
PY = sys.executable
DB_MIGRATION = REPO / "db" / "010_land_upper_stats_v2.sql"


def _log(lines: list[str], msg: str) -> None:
    # Windows cp949 콘솔: 비ASCII는 파일 로그에만 남기고 print는 ASCII 위주
    lines.append(msg)
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _run(cmd: list[str], log_lines: list[str]) -> None:
    _log(log_lines, f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def _table_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT to_regclass(:t) IS NOT NULL"),
            {"t": name},
        ).scalar()
    )


def collect_metrics(phase: str) -> dict:
    eng = get_engine()
    out: dict = {}
    with eng.connect() as conn:
        out["land_transactions_total"] = int(
            conn.execute(text("SELECT COUNT(*) FROM land_transactions")).scalar() or 0
        )
        out["land_transactions_valid"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions "
                    "WHERE is_valid = TRUE AND is_cancelled = FALSE"
                )
            ).scalar()
            or 0
        )
        out["needs_review"] = int(
            conn.execute(
                text("SELECT COUNT(*) FROM land_transactions WHERE needs_review = TRUE")
            ).scalar()
            or 0
        )
        out["empty_beopjungri"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM land_transactions "
                    "WHERE btrim(COALESCE(beopjungri_code::text, '')) = ''"
                )
            ).scalar()
            or 0
        )
        notes = conn.execute(
            text(
                """
                SELECT COALESCE(mapping_notes, '') AS n, COUNT(*)::int AS c
                FROM land_transactions
                WHERE needs_review = TRUE
                GROUP BY 1 ORDER BY c DESC LIMIT 15
                """
            )
        ).fetchall()
        out["mapping_notes_top"] = [(str(r[0]), int(r[1])) for r in notes]

        out["lbs_v2_rows"] = int(
            conn.execute(text("SELECT COUNT(*) FROM land_basic_stats_v2")).scalar() or 0
        )
        if _table_exists(conn, "land_upper_stats_v2"):
            out["lus_v2_rows"] = int(
                conn.execute(text("SELECT COUNT(*) FROM land_upper_stats_v2")).scalar() or 0
            )
        else:
            out["lus_v2_rows"] = None

        # 기암리(岐岩) 샘플 — region_codes 4311132026 · 동일 읍면동(8자리) 거래
        sample = conn.execute(
            text(
                """
                WITH giam AS (
                    SELECT eupmyeondong_code::text AS e8
                    FROM region_codes
                    WHERE btrim(beopjungri_code::text) = '4311132026'
                      AND COALESCE(is_active, TRUE)
                    LIMIT 1
                )
                SELECT
                    COUNT(*)::int AS n,
                    COUNT(*) FILTER (
                        WHERE btrim(lt.beopjungri_code::text) = '4311132026'
                    )::int AS mapped_giam
                FROM land_transactions lt
                CROSS JOIN giam
                WHERE btrim(lt.beopjungri_code::text) = '4311132026'
                   OR btrim(lt.beopjungri_code::text) LIKE giam.e8 || '%'
                """
            )
        ).one()
        out["sample_giam_scope_tx"] = int(sample[0])
        out["sample_giam_mapped_4311132026"] = int(sample[1])

        out["upper_sigungu_43111_sample"] = []
        if _table_exists(conn, "land_upper_stats_v2"):
            upper_giam = conn.execute(
                text(
                    """
                    SELECT region_level, window_years, count, mean
                    FROM land_upper_stats_v2
                    WHERE region_level = 'sigungu'
                      AND region_code = '43111'
                      AND zone_type = 'ALL' AND land_category = 'ALL'
                    ORDER BY as_of_month DESC, window_years
                    LIMIT 3
                    """
                )
            ).fetchall()
            out["upper_sigungu_43111_sample"] = [tuple(r) for r in upper_giam]

    out["phase"] = phase
    return out


def format_metrics(m: dict) -> str:
    lines = [
        f"=== {m.get('phase', '?')} ===",
        f"land_transactions total={m['land_transactions_total']:,} valid={m['land_transactions_valid']:,}",
        f"needs_review={m['needs_review']:,} empty_beopjungri={m['empty_beopjungri']:,}",
        f"land_basic_stats_v2 rows={m['lbs_v2_rows']:,}",
        f"land_upper_stats_v2 rows={m.get('lus_v2_rows')}",
        f"sample 기암리 scope/eup rows={m['sample_giam_scope_tx']} mapped_to_4311132026={m['sample_giam_mapped_4311132026']}",
    ]
    if m.get("mapping_notes_top"):
        lines.append("mapping_notes (needs_review):")
        for note, cnt in m["mapping_notes_top"]:
            lines.append(f"  {note!r}: {cnt:,}")
    if m.get("upper_sigungu_43111_sample"):
        lines.append("upper_stats sigungu 43111 sample: " + str(m["upper_sigungu_43111_sample"]))
    return "\n".join(lines)


def pg_dump_backup(log_lines: list[str]) -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = LOGS / f"backup_land_stats_{ts}.sql"
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL 필요 (pg_dump)")

    # postgresql+psycopg2:// → postgresql://
    pg_url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    cmd = ["pg_dump", pg_url, "-f", str(out_path), "--no-owner", "--no-acl"]
    _log(log_lines, f"pg_dump → {out_path}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        _log(log_lines, "WARN: pg_dump not found - backup skipped (manual backup recommended)")
        return out_path
    return out_path


def apply_upper_migration(log_lines: list[str]) -> None:
    if not DB_MIGRATION.is_file():
        raise SystemExit(f"마이그레이션 없음: {DB_MIGRATION}")
    eng = get_engine()
    with eng.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'land_upper_stats_v2'"
            )
        ).fetchone()
    if exists:
        _log(log_lines, "land_upper_stats_v2 exists - DDL skip")
        return
    _log(log_lines, f"DDL 적용: {DB_MIGRATION}")
    execute_sql_file(eng, str(DB_MIGRATION))


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 DB 재정제·사전집계 재구축")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-01")
    parser.add_argument("--windows", default="3,5")
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--skip-reprocess", action="store_true")
    args = parser.parse_args()

    log_lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _log(log_lines, f"run_local_rebuild 시작 {ts}")

    before = collect_metrics("BEFORE")
    _log(log_lines, format_metrics(before))

    if not args.skip_backup:
        pg_dump_backup(log_lines)

    apply_upper_migration(log_lines)

    if not args.skip_reprocess:
        _run([PY, "clean.py", "--reprocess-all"], log_lines)

    mid = collect_metrics("AFTER_REPROCESS")
    _log(log_lines, format_metrics(mid))

    _run(
        [PY, "build_stats_v2.py", "--as-of", args.as_of, "--windows", args.windows],
        log_lines,
    )
    _run(
        [
            PY,
            "build_upper_stats_v2.py",
            "--as-of",
            args.as_of,
            "--windows",
            args.windows,
        ],
        log_lines,
    )

    after = collect_metrics("AFTER_STATS")
    _log(log_lines, format_metrics(after))

    from run_pipeline import _truncate_paid_caches

    _truncate_paid_caches()
    _log(log_lines, "analysis_cache / analysis_base_cache TRUNCATE 완료")

    log_path = LOGS / f"rebuild_local_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"\n로그 저장: {log_path}")


if __name__ == "__main__":
    main()
