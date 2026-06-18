#!/usr/bin/env python3
"""
토지 재구축 Phase 2~3 야간 마무리 오케스트레이터.

실행 (V1 build_stats 가 이미 돌아가는 중이면 완료까지 대기 후 이어서 실행):
    cd pipeline
    set DATABASE_URL=postgresql+psycopg2://postgres:8972@localhost:5432/land_stats_next
    python finish_land_rebuild.py

산출:
    logs/rebuild_finish_YYYYMMDD.log
    clean_snapshots/rebuild_2021_2026/finish_summary.json
    clean_snapshots/rebuild_2021_2026/land_tx_counts_compare.json
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SNAP_DIR = ROOT / "clean_snapshots" / "rebuild_2021_2026"
LOG_DIR = REPO / "logs"
BACKEND = REPO / "backend"

AS_OF = "2026-06-01"  # 재구축 마무리 고정값 — 월간 SOP와 다를 수 있음. docs/LAND_LEDGER_REBUILD_PLAN.md §12
OLD_DB = os.environ.get("LAND_STATS_OLD_URL", "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats")
NEXT_DB = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats_next"
)
V1_LOG = LOG_DIR / "rebuild_build_stats_2021_2026.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"rebuild_finish_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("finish_rebuild")


def run_step(name: str, cmd: list[str], *, env: dict | None = None, log_file: Path | None = None) -> int:
    log.info("=== STEP %s: %s ===", name, " ".join(cmd))
    merged = {**os.environ, **(env or {})}
    merged.setdefault("DATABASE_URL", NEXT_DB)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"\n\n--- {name} @ {datetime.now().isoformat()} ---\n")
            proc = subprocess.run(cmd, cwd=ROOT, env=merged, stdout=fh, stderr=subprocess.STDOUT)
        return proc.returncode
    proc = subprocess.run(cmd, cwd=ROOT, env=merged)
    return proc.returncode


def wait_for_v1(timeout_sec: int = 6 * 3600, poll_sec: int = 60) -> bool:
    """진행 중인 build_stats.py 완료 대기. 로그에 '사전 집계 완료' 또는 exit 확인."""
    deadline = time.time() + timeout_sec
    log.info("V1 build_stats 완료 대기 (최대 %.0f시간)...", timeout_sec / 3600)
    while time.time() < deadline:
        if V1_LOG.exists():
            body = V1_LOG.read_text(encoding="utf-8", errors="replace")
            if "사전 집계 완료" in body:
                log.info("V1 build_stats 완료 확인 (로그)")
                return True
        # DB 행수로 보조 확인
        try:
            eng = create_engine(NEXT_DB)
            with eng.connect() as c:
                n = c.execute(text("SELECT COUNT(*) FROM land_basic_stats")).scalar()
            if n and int(n) > 100_000:
                log.info("land_basic_stats 행수=%s - V1 완료로 간주", f"{int(n):,}")
                return True
        except Exception as exc:
            log.debug("V1 DB check: %s", exc)
        time.sleep(poll_sec)
    log.error("V1 build_stats 대기 타임아웃")
    return False


def compare_old_new() -> dict:
    eng_old = create_engine(OLD_DB)
    eng_new = create_engine(NEXT_DB)
    q_year = text(
        """
        SELECT contract_year, COUNT(*)::bigint
        FROM land_transactions WHERE is_valid = TRUE
        GROUP BY 1 ORDER BY 1
        """
    )
    q_sido = text(
        """
        SELECT LEFT(beopjungri_code, 2) AS sido, COUNT(*)::bigint
        FROM land_transactions WHERE is_valid = TRUE
        GROUP BY 1 ORDER BY 1
        """
    )
    with eng_old.connect() as c:
        old_by_year = {int(r[0]): int(r[1]) for r in c.execute(q_year)}
        old_by_sido = {r[0]: int(r[1]) for r in c.execute(q_sido)}
        old_total = c.execute(text("SELECT COUNT(*) FROM land_transactions")).scalar()
    with eng_new.connect() as c:
        new_by_year = {int(r[0]): int(r[1]) for r in c.execute(q_year)}
        new_by_sido = {r[0]: int(r[1]) for r in c.execute(q_sido)}
        new_total = c.execute(text("SELECT COUNT(*) FROM land_transactions")).scalar()

    overlap_years = sorted(set(old_by_year) & set(new_by_year))
    year_diff = {
        str(y): {"old": old_by_year[y], "new": new_by_year[y], "delta": new_by_year[y] - old_by_year[y]}
        for y in overlap_years
    }
    out = {
        "generated_at": datetime.now().isoformat(),
        "old_total": int(old_total),
        "new_total": int(new_total),
        "old_year_range": [min(old_by_year), max(old_by_year)] if old_by_year else [],
        "new_year_range": [min(new_by_year), max(new_by_year)] if new_by_year else [],
        "by_year_overlap": year_diff,
        "by_sido_old": old_by_sido,
        "by_sido_new": new_by_sido,
    }
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / "land_tx_counts_compare.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("old/new 비교 저장: %s", path)
    return out


def stats_snapshot() -> dict:
    eng = create_engine(NEXT_DB)
    with eng.connect() as c:
        v1 = c.execute(text("SELECT COUNT(*) FROM land_basic_stats")).scalar()
        v2 = c.execute(
            text(
                "SELECT COUNT(*) FROM land_basic_stats_v2 WHERE as_of_month = :a"
            ),
            {"a": date.fromisoformat(AS_OF)},
        ).scalar()
        upper = c.execute(
            text(
                "SELECT COUNT(*) FROM land_upper_stats_v2 WHERE as_of_month = :a"
            ),
            {"a": date.fromisoformat(AS_OF)},
        ).scalar()
    return {"land_basic_stats": int(v1 or 0), "v2_rows": int(v2 or 0), "upper_v2_rows": int(upper or 0)}


def start_api(port: int = 8001) -> subprocess.Popen:
    env = {**os.environ, "DATABASE_URL": NEXT_DB, "STATS_V2_DEFAULT_AS_OF_MONTH": AS_OF}
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    log.info("API 시작 :%d", port)
    return subprocess.Popen(
        cmd,
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_health(base: str, timeout: int = 120) -> bool:
    url = f"{base.rstrip('/')}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                log.info("health OK: %s", r.json())
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


def main() -> int:
    os.environ["DATABASE_URL"] = NEXT_DB
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict = {"started_at": datetime.now().isoformat(), "as_of_month": AS_OF, "steps": {}}

    # --- Phase 2: V1 wait / dedupe / V2 / upper ---
    if not wait_for_v1():
        log.warning("V1 미완 — build_stats.py 재실행")
        rc = run_step("build_stats", [sys.executable, "build_stats.py"], log_file=LOG_DIR / "rebuild_build_stats_rerun.log")
        summary["steps"]["build_stats_rerun"] = rc
        if rc != 0:
            summary["status"] = "failed_v1"
            _write_summary(summary)
            return 1

    rc = run_step("dedupe", [sys.executable, "dedupe_land_transactions.py", "--execute", "--rehash"])
    summary["steps"]["dedupe"] = rc

    rc = run_step(
        "build_stats_v2",
        [sys.executable, "build_stats_v2.py", "--as-of", AS_OF, "--windows", "3,5"],
        log_file=LOG_DIR / "rebuild_build_stats_v2.log",
    )
    summary["steps"]["build_stats_v2"] = rc
    if rc != 0:
        summary["status"] = "failed_v2"
        _write_summary(summary)
        return 1

    rc = run_step(
        "build_upper_stats_v2",
        [sys.executable, "build_upper_stats_v2.py", "--as-of", AS_OF, "--windows", "3,5"],
        log_file=LOG_DIR / "rebuild_build_upper_v2.log",
    )
    summary["steps"]["build_upper_stats_v2"] = rc
    if rc != 0:
        summary["status"] = "failed_upper_v2"
        _write_summary(summary)
        return 1

    rc = run_step(
        "coverage",
        [sys.executable, "rebuild_land_coverage.py", "--out", str(SNAP_DIR / "national_coverage_final.json")],
    )
    summary["steps"]["coverage"] = rc

    # --- Phase 3: 검증 ---
    summary["compare"] = compare_old_new()
    summary["stats"] = stats_snapshot()

    rc = run_step(
        "verify_monthly_integrity",
        [sys.executable, "verify_monthly_integrity.py", "--as-of-month", AS_OF],
        log_file=LOG_DIR / "rebuild_verify_integrity.log",
    )
    summary["steps"]["verify_monthly_integrity"] = rc

    api_proc = start_api(8001)
    try:
        if wait_health("http://127.0.0.1:8001"):
            rc = run_step(
                "verify_v2_national_samples",
                [
                    sys.executable,
                    "verify_v2_national_samples.py",
                    "--base-url",
                    "http://127.0.0.1:8001",
                    "--as-of-month",
                    AS_OF,
                ],
                log_file=LOG_DIR / "rebuild_verify_v2_samples.log",
            )
            summary["steps"]["verify_v2_national_samples"] = rc
        else:
            log.error("API health 타임아웃")
            summary["steps"]["verify_v2_national_samples"] = -1
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            api_proc.kill()

    failed = [k for k, v in summary["steps"].items() if v not in (0, None)]
    summary["status"] = "ok" if not failed else "completed_with_failures"
    summary["failed_steps"] = failed
    summary["finished_at"] = datetime.now().isoformat()
    _write_summary(summary)
    log.info("finish_land_rebuild 완료 status=%s failed=%s", summary["status"], failed)
    return 0 if summary["status"] == "ok" else 1


def _write_summary(summary: dict) -> None:
    path = SNAP_DIR / "finish_summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info("요약 저장: %s", path)


if __name__ == "__main__":
    raise SystemExit(main())
