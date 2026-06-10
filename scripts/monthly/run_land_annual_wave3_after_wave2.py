#!/usr/bin/env python3
"""
wave2(5시도) ingest 완료 대기 → wave3(잔여 10시도) CSV 수집·정제·장기 추세 연도 마트.

국토부 CSV 일일 ~100건 제한: 다운로드는 --max-new-downloads 100 으로 끊고,
2010~2020 CSV가 **11개 연도 모두 있는 시도만** collect·clean·annual 처리.

예)
  py scripts/monthly/run_land_annual_wave3_after_wave2.py --wait-pid 9444
  py scripts/monthly/run_land_annual_wave3_after_wave2.py --skip-wait --skip-download
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
RAW_DIR = REPO_ROOT / "raw" / "토지_2010_2020"
PY = sys.executable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from land_historical_csv_status import (  # noqa: E402
    HISTORICAL_YEARS,
    assess_wave,
    csv_path,
    ready_sidos,
)

WAVE3 = [
    ("11", "서울특별시"),
    ("26", "부산광역시"),
    ("27", "대구광역시"),
    ("28", "인천광역시"),
    ("29", "광주광역시"),
    ("31", "울산광역시"),
    ("46", "전라남도"),
    ("48", "경상남도"),
    ("50", "제주특별자치도"),
    ("52", "전북특별자치도"),
]

WAVE2_SIDO = ("30", "36", "41", "47", "51")
DEFAULT_MAX_NEW_DOWNLOADS = 100


def setup_logging() -> Path:
    log_dir = PIPELINE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"land_annual_wave3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
        ],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def wait_pid(pid: int, *, poll_sec: int = 90) -> None:
    log = logging.getLogger("wave3")
    log.info("wave2 ingest PID %d 종료 대기 (poll=%ds)", pid, poll_sec)
    while pid_alive(pid):
        log.info("… 아직 실행 중 (PID %d)", pid)
        time.sleep(poll_sec)
    log.info("PID %d 종료 확인", pid)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    log = logging.getLogger("wave3")
    log.info("> %s", " ".join(cmd))
    return subprocess.run(cmd, check=check, cwd=str(cwd or REPO_ROOT))


def wave2_annual_ready() -> tuple[bool, dict[str, tuple]]:
    sys.path.insert(0, str(PIPELINE))
    from sqlalchemy import text  # noqa: WPS433

    from db_utils import get_engine  # noqa: WPS433

    engine = get_engine()
    status: dict[str, tuple] = {}
    ok = True
    with engine.connect() as conn:
        for sc in WAVE2_SIDO:
            row = conn.execute(
                text(
                    """
                    SELECT MIN(calendar_year), MAX(calendar_year), COUNT(*)
                    FROM land_annual_stats
                    WHERE LEFT(btrim(beopjungri_code::text), 2) = :s
                    """
                ),
                {"s": sc},
            ).one()
            status[sc] = row
            if row[0] is None or int(row[0]) > 2010:
                ok = False
    return ok, status


def wait_wave2_annual(*, poll_sec: int = 90) -> None:
    log = logging.getLogger("wave3")
    log.info("wave2 annual(2010~) DB 확인 대기 (poll=%ds)", poll_sec)
    while True:
        ready, status = wave2_annual_ready()
        for sc, row in status.items():
            log.info("wave2 annual sido %s: %s~%s rows=%s", sc, row[0], row[1], row[2])
        if ready:
            log.info("wave2 annual 준비 완료")
            return
        log.info("wave2 annual 미완 — %ds 후 재확인", poll_sec)
        time.sleep(poll_sec)


def verify_wave2_annual() -> None:
    ready, status = wave2_annual_ready()
    log = logging.getLogger("wave3")
    for sc, row in status.items():
        log.info("wave2 annual sido %s: %s~%s rows=%s", sc, row[0], row[1], row[2])
    if not ready:
        bad = next(sc for sc, row in status.items() if row[0] is None or int(row[0]) > 2010)
        row = status[bad]
        raise SystemExit(
            f"wave2 미완료: sido {bad} annual min_year={row[0]} (2010 기대). "
            "wave2 ingest 로그 확인 후 재실행하세요."
        )


def log_wave3_csv_status() -> list[tuple[str, str]]:
    log = logging.getLogger("wave3")
    statuses = assess_wave(RAW_DIR, WAVE3)
    for st in statuses:
        if st.complete:
            log.info("CSV 완료: %s (%s) %d/%d년", st.region, st.sido_code, st.file_count, len(HISTORICAL_YEARS))
        elif st.file_count:
            log.warning(
                "CSV 미완: %s (%s) %d/%d년 - 다음 세션에서 이어 받기",
                st.region,
                st.sido_code,
                st.file_count,
                len(HISTORICAL_YEARS),
            )
        else:
            log.warning("CSV 없음: %s (%s)", st.region, st.sido_code)
    ready = ready_sidos(RAW_DIR, WAVE3)
    log.info("처리 대상(11년 CSV 완비): %d개 시도 %s", len(ready), [sc for sc, _ in ready])
    return ready


def collect_for_regions(regions: list[tuple[str, str]]) -> None:
    log = logging.getLogger("wave3")
    if not regions:
        log.warning("collect 생략 — CSV 완비 시도 없음")
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for _sc, region in regions:
        for year in HISTORICAL_YEARS:
            p = csv_path(RAW_DIR, region, year)
            if p.is_file():
                files.append(p)
    log.info("collect: %d개 CSV (%d 시도)", len(files), len(regions))
    batch = 5
    for i in range(0, len(files), batch):
        chunk = files[i : i + batch]
        run(
            [
                PY,
                str(PIPELINE / "collect.py"),
                "--mode",
                "excel",
                "--format",
                "csv",
                "--file",
                ",".join(str(p) for p in chunk),
            ],
            cwd=PIPELINE,
        )


def build_annual_for_sidos(sido_codes: list[str]) -> None:
    log = logging.getLogger("wave3")
    if not sido_codes:
        log.warning("annual build 생략 — 대상 시도 없음")
        return
    annual_cmd = [PY, str(PIPELINE / "build_annual_stats.py"), "--years", "2010-2026", "--with-upper"]
    for sc in sido_codes:
        annual_cmd.extend(["--sido-code", sc])
    run(annual_cmd, cwd=PIPELINE)


def summarize_national() -> None:
    sys.path.insert(0, str(PIPELINE))
    from sqlalchemy import text  # noqa: WPS433

    from db_utils import get_engine  # noqa: WPS433

    log = logging.getLogger("wave3")
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT LEFT(btrim(beopjungri_code::text), 2) AS sido,
                       COUNT(*), MIN(calendar_year), MAX(calendar_year)
                FROM land_annual_stats
                GROUP BY 1
                ORDER BY 1
                """
            )
        ).fetchall()
    log.info("=== land_annual_stats 전국 요약 ===")
    for row in rows:
        log.info("sido %s: rows=%s years=%s~%s", row[0], row[1], row[2], row[3])
    covered = sum(1 for r in rows if r[2] is not None and int(r[2]) <= 2010 and int(r[3]) >= 2026)
    log.info("2010~2026 커버 시도 수: %d / %d", covered, len(rows))


def main() -> None:
    p = argparse.ArgumentParser(description="wave2 대기 후 wave3 장기추세 backfill")
    p.add_argument("--wait-pid", type=int, default=0, help="(레거시) wave2 ingest PID — --wait-wave2-annual 권장")
    p.add_argument("--skip-wait", action="store_true", help="wave2 대기 생략")
    p.add_argument(
        "--wait-wave2-annual",
        action="store_true",
        help="land_annual_stats 에 wave2 5시도 2010~ 반영될 때까지 DB 폴링",
    )
    p.add_argument("--skip-download", action="store_true", help="CSV 다운로드 생략")
    p.add_argument("--headless", action="store_true", help="Selenium headless")
    p.add_argument(
        "--max-new-downloads",
        type=int,
        default=DEFAULT_MAX_NEW_DOWNLOADS,
        help=f"신규 CSV 다운로드 상한 (0=무제한, 기본 {DEFAULT_MAX_NEW_DOWNLOADS})",
    )
    args = p.parse_args()

    log_path = setup_logging()
    log = logging.getLogger("wave3")
    log.info("로그: %s", log_path)

    if args.wait_wave2_annual and not args.skip_wait:
        wait_wave2_annual()
    elif not args.skip_wait and args.wait_pid:
        wait_pid(args.wait_pid)
    elif not args.skip_wait:
        log.warning("--wait-pid / --wait-wave2-annual 없음 — annual 테이블 즉시 검증")

    verify_wave2_annual()
    log.info("wave2 검증 OK (2010~ annual)")

    if not args.skip_download:
        regions = ",".join(r for _, r in WAVE3)
        dl_cmd = [
            PY,
            str(REPO_ROOT / "scripts" / "monthly" / "download_molit_land_historical_csv.py"),
            "--regions",
            regions,
            "--start-year",
            "2010",
            "--end-year",
            "2020",
        ]
        if args.headless:
            dl_cmd.append("--headless")
        if args.max_new_downloads > 0:
            dl_cmd.extend(["--max-new-downloads", str(args.max_new_downloads)])
        # 100건 제한 등으로 일부만 받아도 계속 진행
        run(dl_cmd, check=False)

    ready = log_wave3_csv_status()
    if not ready:
        log.warning(
            "CSV 11년 완비 시도 없음 — collect/annual 생략. "
            "내일 같은 명령으로 이어 받으면 스킵된 파일부터 진행됩니다."
        )
        summarize_national()
        return

    collect_for_regions(ready)
    run([PY, str(PIPELINE / "clean.py")], cwd=PIPELINE)
    build_annual_for_sidos([sc for sc, _ in ready])

    summarize_national()
    pending = [(sc, r) for sc, r in WAVE3 if (sc, r) not in ready]
    if pending:
        log.info(
            "wave3 부분 완료 - 미처리 %d시도: %s (다음 실행 시 download 재개)",
            len(pending),
            [f"{r}({sc})" for sc, r in pending],
        )
    else:
        log.info("wave3 전체 완료 (10시도)")


if __name__ == "__main__":
    main()
