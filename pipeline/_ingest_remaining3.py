"""Ingest historical CSV for sidos 46, 48, 52 only."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "pipeline"
RAW = REPO / "raw" / "토지_2010_2020"
PY = sys.executable

REGIONS = [
    ("46", "전라남도"),
    ("48", "경상남도"),
    ("52", "전북특별자치도"),
]
YEARS = list(range(2010, 2021))


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(PIPELINE))


def main() -> None:
    files: list[Path] = []
    for _sc, region in REGIONS:
        for year in YEARS:
            p = RAW / f"{region}_토지_매매_{year}.csv"
            if not p.is_file():
                raise SystemExit(f"missing CSV: {p}")
            files.append(p)
    print("skip collect (already loaded)")
    run([PY, "clean.py"])
    annual = [PY, "build_annual_stats.py", "--years", "2010-2026", "--with-upper"]
    for sc, _ in REGIONS:
        annual.extend(["--sido-code", sc])
    run(annual)
    print("done: sidos 46, 48, 52")


if __name__ == "__main__":
    main()
