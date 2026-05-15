"""
충북·경기·충남·경북 이외 시도 — region_codes 시드 → 토지 xlsx 파이프라인 → 인구 연도별 시드.

    cd pipeline
    .\\.venv\\Scripts\\python.exe run_remaining_sidos.py
    .\\.venv\\Scripts\\python.exe run_remaining_sidos.py --dry-run
    .\\.venv\\Scripts\\python.exe run_remaining_sidos.py --resume-from 전라남도

원본: 프로젝트 루트의 원본/토지_<약칭> (폴더 바로 아래 .xlsx 만).
로그: pipeline/logs/remaining_sidos_<YYYYMMDD_HHMMSS>.log (콘솔에도 출력)
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = Path(__file__).resolve().parent
PY = sys.executable

# (seed_region_codes --sido, 인구 codes-prefix, 원본/토지_* 폴더명)
REMAINING: list[tuple[str, str, str]] = [
    ("서울특별시", "11", "토지_서울"),
    ("부산광역시", "26", "토지_부산"),
    ("대구광역시", "27", "토지_대구"),
    ("인천광역시", "28", "토지_인천"),
    ("광주광역시", "29", "토지_광주"),
    ("대전광역시", "30", "토지_대전"),
    ("울산광역시", "31", "토지_울산"),
    ("세종특별자치시", "36", "토지_세종"),
    ("전라남도", "46", "토지_전남"),
    ("경상남도", "48", "토지_경남"),
    ("제주특별자치도", "50", "토지_제주"),
    ("강원특별자치도", "51", "토지_강원"),
    ("전북특별자치도", "52", "토지_전북"),
]


def _setup_logging() -> Path:
    log_dir = PIPELINE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"remaining_sidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="잔여 시도 토지·인구 일괄 적재")
    parser.add_argument("--dry-run", action="store_true", help="명령만 출력")
    parser.add_argument(
        "--resume-from",
        metavar="SIDO",
        help="목록에서 해당 --sido 이름부터 실행 (이전 시도는 건너뜀)",
    )
    args = parser.parse_args()

    log_path = _setup_logging()
    log = logging.getLogger("run_remaining_sidos")
    log.info("로그 파일: %s", log_path)

    region_csv = next((p for p in (ROOT / "data" / "region_codes").glob("*.csv")), None)
    if region_csv is None:
        raise SystemExit("data/region_codes/*.csv 없음")
    pop_dir = ROOT / "data" / "population"

    todo = list(REMAINING)
    if args.resume_from:
        idx = next((i for i, t in enumerate(todo) if t[0] == args.resume_from), None)
        if idx is None:
            raise SystemExit(f"--resume-from '{args.resume_from}' 가 목록에 없음. 사용 가능: {[t[0] for t in REMAINING]}")
        todo = todo[idx:]
        log.info("--resume-from %s → %d개 시도 실행", args.resume_from, len(todo))

    for sido, prefix, folder in todo:
        excel_dir = (ROOT / "원본" / folder).resolve()
        if not excel_dir.is_dir():
            raise SystemExit(f"엑셀 폴더 없음: {excel_dir}")
        xlsx = list(excel_dir.glob("*.xlsx"))
        if not xlsx:
            raise SystemExit(f".xlsx 없음: {excel_dir}")

        log.info("======== 시도 시작: %s (prefix=%s, %d xlsx) ========", sido, prefix, len(xlsx))

        seed_cmd = [
            PY,
            str(PIPELINE / "seed_region_codes.py"),
            "--file",
            str(region_csv),
            "--sido",
            sido,
        ]
        pipe_cmd = [
            PY,
            str(PIPELINE / "run_pipeline.py"),
            "--excel-dir",
            str(excel_dir),
            "--excel-format",
            "auto",
        ]

        if args.dry_run:
            log.info("[dry-run] %s", " ".join(map(str, seed_cmd)))
            log.info("[dry-run] %s", " ".join(map(str, pipe_cmd)))
            if pop_dir.is_dir():
                for csv_path in sorted(pop_dir.glob("*_????????.csv")):
                    pop_cmd = [
                        PY,
                        str(PIPELINE / "seed_population_csv.py"),
                        "--file",
                        str(csv_path),
                        "--codes-prefix",
                        prefix,
                    ]
                    log.info("[dry-run] %s", " ".join(pop_cmd))
            continue

        subprocess.run(seed_cmd, cwd=str(PIPELINE), check=True)
        subprocess.run(pipe_cmd, cwd=str(PIPELINE), check=True)

        if pop_dir.is_dir():
            for csv_path in sorted(pop_dir.glob("*_????????.csv")):
                subprocess.run(
                    [
                        PY,
                        str(PIPELINE / "seed_population_csv.py"),
                        "--file",
                        str(csv_path),
                        "--codes-prefix",
                        prefix,
                    ],
                    cwd=str(PIPELINE),
                    check=True,
                )
        else:
            log.warning("data/population 없음 — 인구 시드 생략")

        log.info("======== 시도 완료: %s ========", sido)


if __name__ == "__main__":
    main()
