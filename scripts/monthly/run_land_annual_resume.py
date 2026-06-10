#!/usr/bin/env python3
"""
장기 추세 backfill 재개 — wave2 마무리 후 wave3 자동 연결.

  py scripts/monthly/run_land_annual_resume.py

wave3는 DB에서 wave2 annual(2010~) 완료를 확인한 뒤 시작 (PID 대기 사용 안 함).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
PY = sys.executable


def setup_logging() -> Path:
    log_dir = PIPELINE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"land_annual_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="wave2 → wave3 장기추세 backfill 재개")
    p.add_argument("--skip-wave2", action="store_true", help="wave2 ingest 생략 (annual 이미 2010~)")
    p.add_argument("--skip-wave3", action="store_true", help="wave3 생략")
    p.add_argument("--headless", action="store_true", help="Selenium headless")
    p.add_argument(
        "--max-new-downloads",
        type=int,
        default=100,
        help="wave3 신규 CSV 상한 (0=무제한)",
    )
    args = p.parse_args()

    log_path = setup_logging()
    log = logging.getLogger("resume")
    log.info("로그: %s", log_path)

    if not args.skip_wave2:
        log.info("=== Step 1: wave2 (5시도 clean + annual) ===")
        subprocess.run(
            [
                PY,
                str(REPO_ROOT / "scripts" / "monthly" / "ingest_land_historical_csv.py"),
                "--skip-collect",
                "--build-annual",
                "--years",
                "2010-2026",
                "--with-upper",
                "--sido-code",
                "30,36,41,47,51",
            ],
            check=True,
            cwd=str(REPO_ROOT),
        )
        log.info("=== Step 1 완료 ===")
    else:
        log.info("Step 1 생략 (--skip-wave2)")

    if not args.skip_wave3:
        log.info("=== Step 2: wave3 (잔여 10시도) ===")
        wave3_cmd = [
            PY,
            str(REPO_ROOT / "scripts" / "monthly" / "run_land_annual_wave3_after_wave2.py"),
            "--skip-wait",
        ]
        if args.headless:
            wave3_cmd.append("--headless")
        if args.max_new_downloads > 0:
            wave3_cmd.extend(["--max-new-downloads", str(args.max_new_downloads)])
        subprocess.run(wave3_cmd, check=False, cwd=str(REPO_ROOT))
        log.info("=== Step 2 종료 ===")

    log.info("run_land_annual_resume.py 종료 — 상세: %s", log_path)


if __name__ == "__main__":
    main()
