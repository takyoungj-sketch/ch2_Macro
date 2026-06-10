"""Re-ingest all Jeonbuk historical CSV (fix missing 2010-2011 annual)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "pipeline"
RAW = REPO / "raw" / "토지_2010_2020"
PY = sys.executable
REGION = "전북특별자치도"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(PIPELINE))


def main() -> None:
    files = [RAW / f"{REGION}_토지_매매_{y}.csv" for y in range(2010, 2021)]
    for p in files:
        if not p.is_file():
            raise SystemExit(f"missing: {p}")
    batch = 5
    for i in range(0, len(files), batch):
        chunk = files[i : i + batch]
        run(
            [
                PY,
                "collect.py",
                "--mode",
                "excel",
                "--format",
                "csv",
                "--file",
                ",".join(str(p) for p in chunk),
            ]
        )
    run([PY, "clean.py"])
    run(
        [
            PY,
            "build_annual_stats.py",
            "--years",
            "2010-2026",
            "--with-upper",
            "--sido-code",
            "52",
        ]
    )
    print("done: jeonbuk 52")


if __name__ == "__main__":
    main()
