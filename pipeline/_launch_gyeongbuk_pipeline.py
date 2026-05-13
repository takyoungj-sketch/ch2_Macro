"""경북 법정동 시드 → 토지_경북 xlsx → collect/clean/build_stats → 인구(prefix 47) 연도별 CSV."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = Path(__file__).resolve().parent
PY = sys.executable

REGION_CODES_CSV = next((p for p in (ROOT / "data" / "region_codes").glob("*.csv")), None)
POP_DIR = ROOT / "data" / "population"


def find_gyeongbuk_excel_dir() -> Path:
    for h in ROOT.iterdir():
        if not h.is_dir():
            continue
        for sub in h.iterdir():
            if not sub.is_dir():
                continue
            xs = [p for p in sub.iterdir() if p.is_file() and p.suffix.lower() == ".xlsx"]
            if xs and all("경상북도" in x.name for x in xs):
                return sub.resolve()
    raise FileNotFoundError("원본 아래 「토지_경북」 등 경상북도 xlsx만 있는 폴더를 찾지 못했습니다.")


def main() -> None:
    if REGION_CODES_CSV is None:
        raise SystemExit("data/region_codes/*.csv 가 없습니다. 법정동 마스터를 두세요.")

    excel_dir = find_gyeongbuk_excel_dir()

    subprocess.run(
        [
            PY,
            str(PIPELINE / "seed_region_codes.py"),
            "--file",
            str(REGION_CODES_CSV),
            "--sido",
            "경상북도",
        ],
        cwd=str(PIPELINE),
        check=True,
    )

    subprocess.run(
        [
            PY,
            str(PIPELINE / "run_pipeline.py"),
            "--excel-dir",
            str(excel_dir),
            "--excel-format",
            "auto",
        ],
        cwd=str(PIPELINE),
        check=True,
    )

    if POP_DIR.is_dir():
        for csv_path in sorted(POP_DIR.glob("*_????????.csv")):
            subprocess.run(
                [
                    PY,
                    str(PIPELINE / "seed_population_csv.py"),
                    "--file",
                    str(csv_path),
                    "--codes-prefix",
                    "47",
                ],
                cwd=str(PIPELINE),
                check=True,
            )


if __name__ == "__main__":
    main()
